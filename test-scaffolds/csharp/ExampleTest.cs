// NUnit scaffold. Class name must match file name and end in Tests.
// For xUnit replace [TestFixture]/[Test] with no attribute / [Fact].
// Replace MyService and placeholder values with real names.

using NUnit.Framework;
using Moq;

namespace MyProject.Tests;

[TestFixture]
public class ExampleTest
{
    private Mock<IDependency> _mockDep = null!;
    private MyService _svc = null!;

    [SetUp]
    public void SetUp()
    {
        _mockDep = new Mock<IDependency>();
        _svc = new MyService(_mockDep.Object);
    }

    [Test]
    public void DoSomething_ValidInput_ReturnsExpectedResult()
    {
        _mockDep.Setup(d => d.Fetch("key")).Returns("value");
        var result = _svc.DoSomething("key");
        Assert.That(result, Is.EqualTo("expected_output"));
    }

    [Test]
    public void DoSomething_NullInput_ThrowsArgumentNullException()
    {
        Assert.That(() => _svc.DoSomething(null!), Throws.ArgumentNullException);
    }

    [Test]
    public async Task DoSomethingAsync_ValidInput_ReturnsExpectedResult()
    {
        _mockDep.Setup(d => d.FetchAsync("key")).ReturnsAsync("async_value");
        var result = await _svc.DoSomethingAsync("key");
        Assert.That(result, Is.EqualTo("async_expected_output"));
    }
}
