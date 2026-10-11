// Optional diagnostic preload, restricted to the owned PX4 process.
#define _GNU_SOURCE
#include <execinfo.h>
#include <signal.h>
#include <unistd.h>
static void trace(int sig) {
    const char msg[]="P0 diagnostic: fatal signal backtrace follows\n";
    write(2,msg,sizeof(msg)-1);
    void *frames[48];int count=backtrace(frames,48);
    backtrace_symbols_fd(frames,count,2);
    signal(sig,SIG_DFL);raise(sig);
}
__attribute__((constructor)) static void setup(void) {
    struct sigaction action={0};action.sa_handler=trace;
    sigemptyset(&action.sa_mask);action.sa_flags=SA_RESETHAND;
    sigaction(SIGSEGV,&action,0);sigaction(SIGABRT,&action,0);
}
