# RSpec scaffold. File must end in _spec.rb.
# Replace MyService and placeholder values with real names.
# Run: bundle exec rspec spec/my_service_spec.rb

require "spec_helper"
require "my_service"

RSpec.describe MyService do
  subject(:svc) { described_class.new(dependency: mock_dep) }
  let(:mock_dep) { instance_double("Dependency", fetch: "mocked_value") }

  describe "#do_something" do
    context "with valid input" do
      it "returns the expected value" do
        expect(svc.do_something("valid_input")).to eq("expected_output")
      end
    end

    context "with empty input" do
      it "raises ArgumentError" do
        expect { svc.do_something("") }.to raise_error(ArgumentError, /must not be empty/)
      end
    end

    context "when dependency returns nil" do
      before { allow(mock_dep).to receive(:fetch).and_return(nil) }

      it "returns a default value" do
        expect(svc.do_something("key")).to eq("default")
      end
    end
  end
end
