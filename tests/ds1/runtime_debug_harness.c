/*
 * Loads the debug dinput8.dll the way the game does, from this program's own
 * folder, and checks that the process has no network afterwards: a name
 * lookup, a TCP connection to a listener of its own and a UDP send all work
 * before the DLL loads and all fail after. Prints one line:
 *   before=<lookup>,<connect>,<send> after=<lookup>,<connect>,<send> loaded=<0|1>
 * where each value is 1 for success and 0 for failure.
 */
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdio.h>

static SOCKET listener;
static struct sockaddr_in where;

static int lookup(void)
{
    struct addrinfo *result = NULL;
    int ok = getaddrinfo("localhost", "80", NULL, &result) == 0;
    if (result)
        freeaddrinfo(result);
    return ok;
}

static int connect_local(void)
{
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    int ok = s != INVALID_SOCKET && connect(s, (struct sockaddr *)&where, sizeof where) == 0;
    if (s != INVALID_SOCKET)
        closesocket(s);
    return ok;
}

static int send_udp(void)
{
    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    int ok = s != INVALID_SOCKET && sendto(s, "x", 1, 0, (struct sockaddr *)&where, sizeof where) == 1;
    if (s != INVALID_SOCKET)
        closesocket(s);
    return ok;
}

int main(void)
{
    WSADATA data;
    WSAStartup(MAKEWORD(2, 2), &data);
    listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    where.sin_family = AF_INET;
    where.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    where.sin_port = 0;
    bind(listener, (struct sockaddr *)&where, sizeof where);
    int size = sizeof where;
    getsockname(listener, (struct sockaddr *)&where, &size);
    listen(listener, 4);

    int before[3] = {lookup(), connect_local(), send_udp()};

    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, path, MAX_PATH);
    while (length && path[length - 1] != L'\\')
        --length;
    path[length] = 0;
    wcscat(path, L"dinput8.dll");
    HMODULE dll = LoadLibraryW(path);
    Sleep(3000); /* dearxan's callback may run on a thread of its own */

    int after[3] = {lookup(), connect_local(), send_udp()};
    printf("before=%d,%d,%d after=%d,%d,%d loaded=%d\n", before[0], before[1], before[2],
           after[0], after[1], after[2], dll != NULL);
    return 0;
}
