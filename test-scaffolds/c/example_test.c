/* GoogleTest scaffold for C — compiled as a C++ test runner calling C under test.
 * Replace my_function and placeholder values with real names.
 * Build: g++ example_test.c -lgtest -lgtest_main -lpthread -o test_runner
 */

#include <gtest/gtest.h>

extern "C" {
#include "my_module.h"  /* the C module under test */
}

TEST(MyFunctionSuite, ReturnsExpectedValueForValidInput) {
    int result = my_function("valid_input");
    EXPECT_EQ(result, 42);
}

TEST(MyFunctionSuite, ReturnsNegativeOneForNullInput) {
    int result = my_function(NULL);
    EXPECT_EQ(result, -1);
}

TEST(MyFunctionSuite, ReturnsNegativeOneForEmptyInput) {
    int result = my_function("");
    EXPECT_EQ(result, -1);
}
