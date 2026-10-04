#define _POSIX_C_SOURCE 200809L
/* Independent C11 evaluator for short-circuit postfix bytecode. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 8192
#define MAX_STACK 256
#define MAX_TOKENS 512

typedef enum { VALUE_INT = 1, VALUE_BOOL = 2 } ValueTag;
typedef struct { ValueTag tag; int64_t payload; } Value;

static int push(Value *stack, size_t *sp, Value value) {
  if (*sp >= MAX_STACK) return 0;
  stack[(*sp)++] = value;
  return 1;
}

static int pop(Value *stack, size_t *sp, Value *value) {
  if (*sp == 0) return 0;
  *value = stack[--(*sp)];
  return 1;
}

static int peek(Value *stack, size_t sp, Value *value) {
  if (sp == 0) return 0;
  *value = stack[sp - 1];
  return 1;
}

static int parse_skip(const char *token, const char *prefix, size_t *skip) {
  size_t n = strlen(prefix);
  if (strncmp(token, prefix, n) != 0 || token[n] != ':') return 0;
  errno = 0;
  char *end = NULL;
  uintmax_t value = strtoumax(token + n + 1, &end, 10);
  if (errno != 0 || end == token + n + 1 || *end != '\0' || value > MAX_TOKENS) return -1;
  *skip = (size_t)value;
  return 1;
}

int main(void) {
  char line[MAX_LINE];
  while (fgets(line, sizeof(line), stdin) != NULL) {
    char *tokens[MAX_TOKENS];
    size_t token_count = 0;
    char *save = NULL;
    char *token = strtok_r(line, " \t\r\n", &save);
    while (token != NULL && token_count < MAX_TOKENS) {
      tokens[token_count++] = token;
      token = strtok_r(NULL, " \t\r\n", &save);
    }
    if (token != NULL || token_count == 0) {
      puts("ERR");
      continue;
    }

    Value stack[MAX_STACK];
    size_t sp = 0;
    int failed = 0;
    size_t pc = 0;
    while (pc < token_count && !failed) {
      token = tokens[pc];
      if (strncmp(token, "I:", 2) == 0) {
        errno = 0;
        char *end = NULL;
        intmax_t parsed = strtoimax(token + 2, &end, 10);
        if (errno != 0 || end == token + 2 || *end != '\0' ||
            parsed < INT64_MIN || parsed > INT64_MAX ||
            !push(stack, &sp, (Value){VALUE_INT, (int64_t)parsed})) {
          failed = 1;
        }
        pc += 1;
        continue;
      }

      size_t skip = 0;
      int sc_and = parse_skip(token, "SCAND", &skip);
      int sc_or = parse_skip(token, "SCOR", &skip);
      if (sc_and == -1 || sc_or == -1) {
        failed = 1;
        continue;
      }
      if (sc_and == 1 || sc_or == 1) {
        Value left;
        if (!peek(stack, sp, &left) || left.tag != VALUE_BOOL ||
            pc + skip + 1 >= token_count) {
          failed = 1;
          continue;
        }
        int decided = (sc_and == 1 && left.payload == 0) ||
                      (sc_or == 1 && left.payload != 0);
        if (decided) {
          /* Skip the right segment and its final AND/OR opcode. */
          pc += skip + 2;
        } else {
          pc += 1;
        }
        continue;
      }

      if (strcmp(token, "NOT") == 0) {
        Value a;
        if (!pop(stack, &sp, &a) || a.tag != VALUE_BOOL ||
            !push(stack, &sp, (Value){VALUE_BOOL, !a.payload})) failed = 1;
        pc += 1;
        continue;
      }

      Value a, b;
      if (!pop(stack, &sp, &b) || !pop(stack, &sp, &a)) {
        failed = 1;
        continue;
      }
      if (strcmp(token, "AND") == 0 || strcmp(token, "OR") == 0) {
        if (a.tag != VALUE_BOOL || b.tag != VALUE_BOOL) {
          failed = 1;
        } else {
          int64_t value = strcmp(token, "AND") == 0
                              ? (a.payload != 0 && b.payload != 0)
                              : (a.payload != 0 || b.payload != 0);
          if (!push(stack, &sp, (Value){VALUE_BOOL, value})) failed = 1;
        }
      } else if (strcmp(token, "EQ") == 0 || strcmp(token, "NE") == 0 ||
                 strcmp(token, "LT") == 0 || strcmp(token, "LE") == 0 ||
                 strcmp(token, "GT") == 0 || strcmp(token, "GE") == 0) {
        if (a.tag != VALUE_INT || b.tag != VALUE_INT) {
          failed = 1;
        } else {
          int64_t value = 0;
          if (strcmp(token, "EQ") == 0) value = a.payload == b.payload;
          else if (strcmp(token, "NE") == 0) value = a.payload != b.payload;
          else if (strcmp(token, "LT") == 0) value = a.payload < b.payload;
          else if (strcmp(token, "LE") == 0) value = a.payload <= b.payload;
          else if (strcmp(token, "GT") == 0) value = a.payload > b.payload;
          else value = a.payload >= b.payload;
          if (!push(stack, &sp, (Value){VALUE_BOOL, value})) failed = 1;
        }
      } else if (strcmp(token, "DIV") == 0) {
        if (a.tag != VALUE_INT || b.tag != VALUE_INT || b.payload == 0 ||
            (a.payload == INT64_MIN && b.payload == -1)) {
          failed = 1;
        } else if (!push(stack, &sp, (Value){VALUE_INT, a.payload / b.payload})) {
          failed = 1;
        }
      } else {
        failed = 1;
      }
      pc += 1;
    }

    if (failed || sp != 1) {
      puts("ERR");
    } else if (stack[0].tag == VALUE_BOOL) {
      printf("B:%" PRId64 "\n", (int64_t)(stack[0].payload != 0));
    } else if (stack[0].tag == VALUE_INT) {
      printf("I:%" PRId64 "\n", stack[0].payload);
    } else {
      puts("ERR");
    }
  }
  return 0;
}
