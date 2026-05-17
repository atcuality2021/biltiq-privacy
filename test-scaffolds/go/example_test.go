package mypackage_test

// go test scaffold — tests live in a _test.go file in the same directory.
// Function names must start with Test (capital T). Replace MyService and
// placeholder values with real names.

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/assert" // optional; stdlib t.Errorf also works
	"yourmodule/mypackage"
)

func TestMyService_DoSomething_ReturnsExpectedValue(t *testing.T) {
	svc := mypackage.NewMyService()
	got, err := svc.DoSomething("valid_input")
	assert.NoError(t, err)
	assert.Equal(t, "expected_output", got)
}

func TestMyService_DoSomething_ErrorOnEmptyInput(t *testing.T) {
	svc := mypackage.NewMyService()
	_, err := svc.DoSomething("")
	if !errors.Is(err, mypackage.ErrEmptyInput) {
		t.Errorf("expected ErrEmptyInput, got %v", err)
	}
}

func TestMyService_DoSomething_Parallel(t *testing.T) {
	t.Parallel()
	svc := mypackage.NewMyService()
	got, err := svc.DoSomething("parallel_input")
	assert.NoError(t, err)
	assert.Equal(t, "parallel_output", got)
}
