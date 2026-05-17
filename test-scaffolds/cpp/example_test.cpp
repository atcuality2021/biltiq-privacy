// GoogleTest scaffold for C++.
// Replace MyService and placeholder values with real names.
// Build: g++ example_test.cpp -lgtest -lgtest_main -lpthread -o test_runner

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include "my_service.h"

class MockDependency : public IDependency {
public:
    MOCK_METHOD(std::string, fetch, (const std::string& key), (override));
};

class MyServiceTest : public ::testing::Test {
protected:
    MockDependency mock_dep_;
    MyService svc_{&mock_dep_};
};

TEST_F(MyServiceTest, ReturnsExpectedValueForValidInput) {
    EXPECT_CALL(mock_dep_, fetch("key")).WillOnce(testing::Return("value"));
    EXPECT_EQ(svc_.doSomething("key"), "expected_output");
}

TEST_F(MyServiceTest, ThrowsForEmptyInput) {
    EXPECT_THROW(svc_.doSomething(""), std::invalid_argument);
}

TEST(MyServiceStandaloneTest, CanBeConstructedWithoutDependency) {
    MyService svc;
    EXPECT_FALSE(svc.isConnected());
}
