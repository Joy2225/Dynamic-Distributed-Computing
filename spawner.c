#include <stdio.h>
#include <windows.h>

#define NUM_PROCESSES 3

int main() {
    const char *baseCommand = "poetry run";
    const char *script = "..\\client.py";

    char command[256];
    snprintf(command, sizeof(command), "%s %s", baseCommand, script);

    STARTUPINFO si[NUM_PROCESSES];
    PROCESS_INFORMATION pi[NUM_PROCESSES];

    for (int i = 0; i < NUM_PROCESSES; i++) {
        ZeroMemory(&si[i], sizeof(si[i]));
        si[i].cb = sizeof(si[i]);
        ZeroMemory(&pi[i], sizeof(pi[i]));

        if (!CreateProcess(
                NULL,
                command,
                NULL,
                NULL,
                FALSE,
                0,
                NULL,
                NULL,
                &si[i],
                &pi[i]
        )) {
            printf("Failed to create process %d.\n", i);
            for (int j = 0; j < i; j++) {
                CloseHandle(pi[j].hProcess);
                CloseHandle(pi[j].hThread);
            }
            return 1;
        }
    }

    for (int i = 0; i < NUM_PROCESSES; i++) {
        WaitForSingleObject(pi[i].hProcess, INFINITE);
    }

    for (int i = 0; i < NUM_PROCESSES; i++) {
        CloseHandle(pi[i].hProcess);
        CloseHandle(pi[i].hThread);
    }

    return 0;
}
