import contextlib
import io
import socket
import traceback
import dill
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

client_key = RSA.generate(2048)
client_public_key = client_key.publickey()
client_cipher = PKCS1_OAEP.new(client_key)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 9876))

s.send(client_public_key.export_key())

server_public_key_data = s.recv(2 << 20)
server_public_key = RSA.import_key(server_public_key_data)
server_cipher = PKCS1_OAEP.new(server_public_key)

while True:
    try:
        encrypted_data = s.recv(2 << 20)
    except ConnectionResetError:
        break
    if not encrypted_data:
        break

    decrypted_data = client_cipher.decrypt(encrypted_data)
    data = dill.loads(decrypted_data)

    print("Code to be executed:")
    print(data["code"])
    print("-" * 50)

    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            exec(data["code"], globs := data["variables"])
        except Exception as e:
            traceback.print_exc()

    result = {
        "stdout": out.getvalue(),
        "variables": globs
    }

    encrypted_result = server_cipher.encrypt(dill.dumps(result))
    s.send(encrypted_result)
