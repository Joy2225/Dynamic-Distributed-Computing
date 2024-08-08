import inspect
import dill
import re
import socket
import sys
import time
import builtins
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from threading import Thread, Lock
from inspect import currentframe

server_key = RSA.generate(2048)
server_public_key = server_key.publickey()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("127.0.0.1", 9876))
server.listen(20)

DEBUG = True
space = re.compile(r"^\s*")


class TempVar:
    def __repr__(self):
        return "uncomputed"


def wait_for_n_executors(n):
    while len(Executor.client_list) < n:
        time.sleep(0)


class Executor:
    ctx_no = 0
    locks = {}

    client_list = []
    client_public_keys = {}
    server = server

    def __enter__(self):
        sys.settrace(lambda *args, **kwargs: None)
        inspect.currentframe().f_back.f_trace = self.trace
        Executor.ctx_no += 1
        self.ctx_no = Executor.ctx_no

    @classmethod
    def accept_clients(cls):
        while True:
            client, _ = cls.server.accept()
            client.send(server_public_key.export_key())
            client_public_key_data = client.recv(2 << 20)
            client_public_key = RSA.import_key(client_public_key_data)
            cls.client_public_keys[client] = client_public_key
            cls.client_list.append(client)

    def trace(*args):
        raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        cf = currentframe()
        start = cf.f_back.f_lineno
        file = cf.f_back.f_code.co_filename

        with open(file) as f:
            lines = f.readlines()[start:]
        index, depth, code = 0, space.match(lines[0]).end(), ["def isolate():\n"]

        while index < len(lines) and lines[index][:depth].isspace():
            code.append(lines[index][depth:])
            index += 1

        exec("\t".join(code), globs := {})
        code_obj = globs["isolate"].__code__
        lvars = set(code_obj.co_varnames)
        names = set(code_obj.co_names) - set(dir(builtins))
        pglobs = cf.f_back.f_globals
        values = {name: pglobs[name] for name in names if name in pglobs}

        if DEBUG:
            print("-" * 50)
            print(f"Execution #", Executor.ctx_no, sep="")
            print("-" * 50)
            print("Variables to send -", values)
            print("Variables to compute -", lvars)
            print("Code to be executed:")

        remote_code = "".join(code[1:])

        if DEBUG:
            print(remote_code)

        tvars = [vname for vname, vvalue in values.items() if isinstance(vvalue, TempVar)]
        if DEBUG:
            if tvars:
                print("Note: Won't proceed until the following variables are computed - ", end="")
                print(set(tvars))
                print("-" * 50)

        for vname in lvars:
            pglobs[vname] = TempVar()

        Thread(target=self.fake_execute, args=(remote_code, values, pglobs, tvars, lvars, names)).start()

        return True

    def fake_execute(self, remote_code, globs, old_globs, waiters, left_vars, check_vars):
        if DEBUG:
            print("\n" + "-" * 50)
            if waiters:
                print("Waiting for the following variables to be computed -", set(waiters))

        while any(isinstance(old_globs[name], TempVar) for name in waiters):
            pass

        while not self.client_list:
            time.sleep(0)

        client_socket = self.client_list[self.ctx_no % len(self.client_list)]

        for key, lock in self.locks.items():
            if set(key) & check_vars:
                break
        else:
            lock, key = Lock(), tuple(sorted(left_vars))
            self.locks[key] = lock
        self.locks[key].acquire()

        for name in waiters:
            globs[name] = old_globs[name]

        if DEBUG:
            if waiters:
                print("All variables computed, ", end="")

            print(f"Starting Execution #", self.ctx_no, sep="")
            print("-" * 50)

        client_public_key = self.client_public_keys[client_socket]
        client_cipher = PKCS1_OAEP.new(client_public_key)

        remote_code_bytes = dill.dumps({"code": remote_code, "variables": globs})
        encrypted_data = client_cipher.encrypt(remote_code_bytes)
        client_socket.send(encrypted_data)

        server_cipher = PKCS1_OAEP.new(server_key)
        encrypted_response = client_socket.recv(2 << 20)
        decrypted_response = server_cipher.decrypt(encrypted_response)
        data = dill.loads(decrypted_response)

        output = data["stdout"]
        globs = data["variables"]

        old_globs.update(globs)
        print(output, end="")
        if DEBUG:
            print("-" * 50)

        self.locks[key].release()


Thread(target=Executor.accept_clients, daemon=True).start()
