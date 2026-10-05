// Package authflow contains the evidence-bounded authenticated login transition.
package authflow

import "fmt"

const (
	IdentityUnknown = "UNKNOWN"

	failedBodySHA256     = "9d131ddf1c0deb56ecded575bbfcee879a12cf10678c6419195b11866dadc791"
	failedHeadersSHA256  = "74a0ec5dcd264443c66be6dd17bf997bfbfa6af7de407f329148f7e7c4872a1c"
	successBodySHA256    = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	successHeadersSHA256 = "48a929df39e9ad187f5422108cb8f4479cc9e7332334d187f335f045ccc731f6"
)

type Response struct {
	RequestMethod string
	Status        int
	Location      string
	BodySHA256    string
	HeadersSHA256 string
	BodyBytes     int
	Identity      string
}

type Contract struct {
	RequestMethod string
	Status        int
	Location      string
	BodySHA256    string
	HeadersSHA256 string
	BodyBytes     int
}

var FailedLoginContract = Contract{
	RequestMethod: "POST", Status: 200, BodySHA256: failedBodySHA256,
	HeadersSHA256: failedHeadersSHA256, BodyBytes: 745,
}

var SuccessfulSubmitContract = Contract{
	RequestMethod: "POST", Status: 302, Location: "/security_check?page=0",
	BodySHA256: successBodySHA256, HeadersSHA256: successHeadersSHA256,
	BodyBytes: 0,
}

func FailedLoginResponse() Response {
	return responseFrom(FailedLoginContract)
}

func SuccessfulSubmitResponse() Response {
	return responseFrom(SuccessfulSubmitContract)
}

func responseFrom(contract Contract) Response {
	return Response{
		RequestMethod: contract.RequestMethod, Status: contract.Status,
		Location: contract.Location, BodySHA256: contract.BodySHA256,
		HeadersSHA256: contract.HeadersSHA256, BodyBytes: contract.BodyBytes,
		Identity: IdentityUnknown,
	}
}

func (c Contract) Validate(actual Response) error {
	if actual.RequestMethod != c.RequestMethod {
		return fmt.Errorf("method = %q, want %q", actual.RequestMethod, c.RequestMethod)
	}
	if actual.Status != c.Status {
		return fmt.Errorf("status = %d, want %d", actual.Status, c.Status)
	}
	if actual.Location != c.Location {
		return fmt.Errorf("location = %q, want %q", actual.Location, c.Location)
	}
	if actual.BodySHA256 != c.BodySHA256 {
		return fmt.Errorf("body SHA-256 = %q, want %q", actual.BodySHA256, c.BodySHA256)
	}
	if actual.HeadersSHA256 != c.HeadersSHA256 {
		return fmt.Errorf("headers SHA-256 = %q, want %q", actual.HeadersSHA256, c.HeadersSHA256)
	}
	if actual.BodyBytes != c.BodyBytes {
		return fmt.Errorf("body bytes = %d, want %d", actual.BodyBytes, c.BodyBytes)
	}
	return nil
}
