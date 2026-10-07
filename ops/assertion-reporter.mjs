// Structured Node test evidence; never includes assertion values or secrets.
export default async function* report(events) {
  for await (const event of events) {
    if (event.type !== "test:fail") continue;
    const error = event.data.details?.error;
    let assertion = false;
    for (let cause = error, depth = 0; cause && depth < 4; cause = cause.cause, depth++) {
      if (cause.code === "ERR_ASSERTION" || cause.name === "AssertionError") assertion = true;
    }
    yield JSON.stringify({ type: event.type, name: event.data.name, assertion,
      failure_type: error?.failureType }) + "\n";
  }
}
