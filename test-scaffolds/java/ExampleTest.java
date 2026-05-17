package com.example.mypackage;

// JUnit 5 scaffold. Class name must match file name and end in Test.
// Replace MyService and placeholder values with real names.

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ExampleTest {

    @Mock
    private DependencyClient dependencyClient;

    private MyService svc;

    @BeforeEach
    void setUp() {
        svc = new MyService(dependencyClient);
    }

    @Test
    void shouldReturnExpectedValueForValidInput() {
        when(dependencyClient.fetch("key")).thenReturn("value");
        String result = svc.doSomething("key");
        assertThat(result).isEqualTo("expected_output");
    }

    @Test
    void shouldThrowIllegalArgumentExceptionForNullInput() {
        assertThatThrownBy(() -> svc.doSomething(null))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("input must not be null");
    }
}
