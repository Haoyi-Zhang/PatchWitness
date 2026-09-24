#define _POSIX_C_SOURCE 200809L
/* Independent C11 postfix evaluator for bounded source-frontend validation. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 8192
#define MAX_STACK 256

static int push(int64_t *stack, size_t *sp, int64_t value) {
  if (*sp >= MAX_STACK) return 0;
  stack[(*sp)++] = value;
  return 1;
}

static int pop(int64_t *stack, size_t *sp, int64_t *value) {
  if (*sp == 0) return 0;
  *value = stack[--(*sp)];
  return 1;
}

int main(void) {
  char line[MAX_LINE];
  while (fgets(line, sizeof(line), stdin) != NULL) {
    int64_t stack[MAX_STACK];
    size_t sp = 0;
    int failed = 0;
    char *save = NULL;
    char *token = strtok_r(line, " \t\r\n", &save);
    while (token != NULL && !failed) {
      if (strncmp(token, "I:", 2) == 0) {
        errno = 0;
        char *end = NULL;
        intmax_t value = strtoimax(token + 2, &end, 10);
        if (errno != 0 || end == token + 2 || *end != '\0' || !push(stack, &sp, (int64_t)value)) failed = 1;
      } else if (strcmp(token, "NOT") == 0) {
        int64_t a;
        if (!pop(stack, &sp, &a) || !push(stack, &sp, !a)) failed = 1;
      } else {
        int64_t a, b, value = 0;
        if (!pop(stack, &sp, &b) || !pop(stack, &sp, &a)) {
          failed = 1;
        } else if (strcmp(token, "AND") == 0) value = (a != 0) && (b != 0);
        else if (strcmp(token, "OR") == 0) value = (a != 0) || (b != 0);
        else if (strcmp(token, "EQ") == 0) value = a == b;
        else if (strcmp(token, "NE") == 0) value = a != b;
        else if (strcmp(token, "LT") == 0) value = a < b;
        else if (strcmp(token, "LE") == 0) value = a <= b;
        else if (strcmp(token, "GT") == 0) value = a > b;
        else if (strcmp(token, "GE") == 0) value = a >= b;
        else if (strcmp(token, "DIV") == 0) {
          if (b == 0 || (a == INT64_MIN && b == -1)) failed = 1;
          else value = a / b;
        } else failed = 1;
        if (!failed && !push(stack, &sp, value)) failed = 1;
      }
      token = strtok_r(NULL, " \t\r\n", &save);
    }
    if (failed || sp != 1) {
      puts("ERR");
    } else {
      printf("%" PRId64 "\n", stack[0]);
    }
  }
  return 0;
}
