extern int shared_value;
extern int square(int);
int answer(void) { return square(shared_value); }
