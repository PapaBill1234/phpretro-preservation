package authflow

import "testing"

func TestFailedLoginResponseContract(t *testing.T) {
	actual := FailedLoginResponse()
	if err := FailedLoginContract.Validate(actual); err != nil {
		t.Fatalf("failed login response: %v", err)
	}
	if actual.Identity != IdentityUnknown {
		t.Fatalf("identity state = %q, want UNKNOWN", actual.Identity)
	}
}

func TestSuccessfulSubmitRedirectContract(t *testing.T) {
	actual := SuccessfulSubmitResponse()
	if err := SuccessfulSubmitContract.Validate(actual); err != nil {
		t.Fatalf("successful submit response: %v", err)
	}
	if actual.Identity != IdentityUnknown {
		t.Fatalf("identity state = %q, want UNKNOWN", actual.Identity)
	}
}

func TestResponseContractRejectsWrongMethod(t *testing.T) {
	actual := FailedLoginResponse()
	actual.RequestMethod = "GET"
	if err := FailedLoginContract.Validate(actual); err == nil {
		t.Fatal("expected wrong method to be rejected")
	}
}

func TestResponseContractRejectsWrongStatus(t *testing.T) {
	actual := SuccessfulSubmitResponse()
	actual.Status = 200
	if err := SuccessfulSubmitContract.Validate(actual); err == nil {
		t.Fatal("expected wrong status to be rejected")
	}
}

func TestResponseContractRejectsWrongRedirect(t *testing.T) {
	actual := SuccessfulSubmitResponse()
	actual.Location = "/account"
	if err := SuccessfulSubmitContract.Validate(actual); err == nil {
		t.Fatal("expected wrong redirect to be rejected")
	}
}

func TestIdentityIsNotClaimedWithoutEvidence(t *testing.T) {
	failed := FailedLoginResponse()
	success := SuccessfulSubmitResponse()
	if failed.Identity != IdentityUnknown || success.Identity != IdentityUnknown {
		t.Fatal("authflow response contract must not claim identity without evidence")
	}
}
