/* Linux-only evaluation fault: stop AFTER the chosen successful atomic rename.
 * The controller SIGKILLs the real process group, bypassing Python rollback.
 * No production binary/source is modified and no success output is fabricated.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void boundary(const char *path, int result) {
    const char *target = getenv("KB_EVAL_STOP_DEST");
    const char *marker = getenv("KB_EVAL_STOP_MARKER");
    if (result || !target || !marker || strcmp(path, target)) return;
    int fd = open(marker, O_CREAT | O_WRONLY | O_EXCL, 0600);
    if (fd < 0) return;
    char value[80];
    int length = snprintf(value, sizeof(value), "%ld\n", (long)getpid());
    int saved = write(fd, value, (size_t)length) == length && fsync(fd) == 0;
    close(fd);
    if (!saved) {
        unlink(marker);
        return;
    }
    raise(SIGSTOP);
}
int rename(const char *old, const char *next) {
    static int (*real_rename)(const char *, const char *);
    if (!real_rename) real_rename = dlsym(RTLD_NEXT, "rename");
    int result = real_rename(old, next);
    boundary(next, result);
    return result;
}
int renameat(int oldfd, const char *old, int nextfd, const char *next) {
    static int (*real_renameat)(int, const char *, int, const char *);
    if (!real_renameat) real_renameat = dlsym(RTLD_NEXT, "renameat");
    int result = real_renameat(oldfd, old, nextfd, next);
    boundary(next, result);
    return result;
}
