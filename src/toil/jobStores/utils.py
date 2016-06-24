import logging
from contextlib import contextmanager

import time

log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def never(exception):
    return False


def retry(delays=(0, 1, 1, 4, 16, 64), timeout=300, predicate=never):
    """
    Retry an operation while the failure matches a given predicate and until a given timeout
    expires, waiting a given amount of time in between attempts. This function is a generator
    that yields contextmanagers. See doctests below for example usage.

    :param Iterable[float] delays: an interable yielding the time in seconds to wait before each
           retried attempt, the last element of the iterable will be repeated.

    :param float timeout: a overall timeout that should not be exceeded for all attempts together.
           This is a best-effort mechanism only and it won't abort an ongoing attempt, even if the
           timeout expires during that attempt.

    :param Callable[[Exception],bool] predicate: a unary callable returning True if another
           attempt should be made to recover from the given exception. The default value for this
           parameter will prevent any retries!

    :return: a generator yielding context managers, one per attempt
    :rtype: Iterator

    Retry for a limited amount of time:

    >>> true = lambda _:True
    >>> false = lambda _:False
    >>> i = 0
    >>> for attempt in retry( delays=[0], timeout=.1, predicate=true ):
    ...     with attempt:
    ...         i += 1
    ...         raise RuntimeError('foo')
    Traceback (most recent call last):
    ...
    RuntimeError: foo
    >>> i > 1
    True

    If timeout is 0, do exactly one attempt:

    >>> i = 0
    >>> for attempt in retry( timeout=0 ):
    ...     with attempt:
    ...         i += 1
    ...         raise RuntimeError( 'foo' )
    Traceback (most recent call last):
    ...
    RuntimeError: foo
    >>> i
    1

    Don't retry on success:

    >>> i = 0
    >>> for attempt in retry( delays=[0], timeout=.1, predicate=true ):
    ...     with attempt:
    ...         i += 1
    >>> i
    1

    Don't retry on unless predicate returns True:

    >>> i = 0
    >>> for attempt in retry( delays=[0], timeout=.1, predicate=false):
    ...     with attempt:
    ...         i += 1
    ...         raise RuntimeError( 'foo' )
    Traceback (most recent call last):
    ...
    RuntimeError: foo
    >>> i
    1
    """
    if timeout > 0:
        go = [None]

        @contextmanager
        def repeated_attempt(delay):
            try:
                yield
            except Exception as e:
                if time.time() + delay < expiration and predicate(e):
                    log.info('Got %s, trying again in %is.', e, delay)
                    time.sleep(delay)
                else:
                    raise
            else:
                go.pop()

        delays = iter(delays)
        expiration = time.time() + timeout
        delay = next(delays)
        while go:
            yield repeated_attempt(delay)
            delay = next(delays, delay)
    else:
        @contextmanager
        def single_attempt():
            yield

        yield single_attempt()


def log_component_failure(e, log, name, attemptNum, maxAttempts=5):
    log.exception('The following exception was raised during deletion:\n%s',
                  e.message, exc_info=True)
    if attemptNum >= maxAttempts:
        log.error("Too many attempts to delete '%s'. Giving up.", name)
        return True
    else:
        log.debug("Retrying deletion for '%s'...", name)
        return False


def log_delete_completed(log, locator, existed, failure):
    if existed and not failure:
        log.info("Successfully deleted job store at location '%s'.", locator)
    elif not existed:
        log.info("No job store found at location '%s'.", locator)
    elif failure:
        log.error("Completed job store deletion at location '%s' with errors see log for details.",
                  locator)
