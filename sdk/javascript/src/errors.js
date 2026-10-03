/** Base class for all GreyGuard SDK errors. */
export class GreyGuardError extends Error {
  constructor(message, options = {}) {
    super(message, options)
    this.name = new.target.name
  }
}

/** The supplied agent identity or credential was rejected. */
export class AuthenticationError extends GreyGuardError {}

/** The authenticated agent is not authorized for the action. */
export class AuthorizationError extends GreyGuardError {}

/** Local scope validation rejected an action before transmission. */
export class ScopeValidationError extends GreyGuardError {}

/** GreyGuard could not complete an API request. */
export class RequestError extends GreyGuardError {
  constructor(message, { statusCode = null, details = null, cause } = {}) {
    super(message, cause === undefined ? {} : { cause })
    this.statusCode = statusCode
    this.details = details
  }
}
