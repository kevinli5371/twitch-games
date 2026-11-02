// Share an in-flight poll within one workspace epoch; a workspace change starts fresh.
export function createRefreshRunner(run, getEpoch) {
  let active;
  return function refresh({force = false} = {}) {
    const epoch = getEpoch();
    if (!force && active?.epoch === epoch) return active.promise;
    const flight = {epoch};
    active = flight;
    flight.promise = Promise.resolve().then(run).finally(() => {
      if (active === flight) active = null;
    });
    return flight.promise;
  };
}
