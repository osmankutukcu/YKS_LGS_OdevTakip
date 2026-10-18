/**
 * V10 narrowly scoped fallback policy.
 * Only transient/unavailable delta protocol failures may use a validated V8
 * full snapshot. Authentication, wrong database, and integrity failures MUST
 * remain terminal. Does not mutate IndexedDB or the outbox.
 */
(function (window) {
    'use strict';
    const ELIGIBLE = new Set([404, 410, 503]);
    function canUseFullSnapshot(error) {
        return Boolean(error && Number.isInteger(error.httpStatus) &&
            ELIGIBLE.has(error.httpStatus));
    }
    window.OfflineResilienceV10 = Object.freeze({canUseFullSnapshot});
})(window);
