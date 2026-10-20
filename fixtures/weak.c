__attribute__((weak)) int square(int x) { return x + 1; }
extern int optional(void) __attribute__((weak));
int use_optional(void) { return optional ? optional() : 0; }
