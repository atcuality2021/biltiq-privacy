<?php

declare(strict_types=1);

// PHPUnit scaffold. Class name must match file name and extend TestCase.
// Replace MyService and placeholder values with real names.
// Run: ./vendor/bin/phpunit tests/ExampleTest.php

namespace App\Tests;

use App\MyService;
use App\Contracts\DependencyInterface;
use PHPUnit\Framework\TestCase;
use PHPUnit\Framework\MockObject\MockObject;

final class ExampleTest extends TestCase
{
    private MockObject $mockDep;
    private MyService $svc;

    protected function setUp(): void
    {
        $this->mockDep = $this->createMock(DependencyInterface::class);
        $this->svc = new MyService($this->mockDep);
    }

    public function testDoSomethingReturnsExpectedValueForValidInput(): void
    {
        $this->mockDep->method('fetch')->with('key')->willReturn('value');
        $result = $this->svc->doSomething('key');
        $this->assertEquals('expected_output', $result);
    }

    public function testDoSomethingThrowsForEmptyInput(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('must not be empty');
        $this->svc->doSomething('');
    }
}
