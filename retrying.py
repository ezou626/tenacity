## Copyright 2013 Ray Holder
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
## http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

import random
import sys
import time

def retry(stop='never_stop', stop_max_attempt_number=5, stop_max_delay=100,
          wait='no_sleep',
          wait_fixed=1000,
          wait_random_min=0, wait_random_max=1000,
          wait_incrementing_start=0, wait_incrementing_increment=100,
          wait_exponential_multiplier=100, wait_exponential_max=5000,
          retry_on_exception=None,
          retry_on_result=None):
    def wrap(f):
        def wrapped_f(*args, **kw):
            return Retrying(
                stop=stop,
                stop_max_attempt_number=stop_max_attempt_number,
                stop_max_delay=stop_max_delay,
                wait=wait,
                wait_fixed=wait_fixed,
                wait_random_min=wait_random_min,
                wait_random_max=wait_random_max,
                wait_incrementing_start=wait_incrementing_start,
                wait_incrementing_increment=wait_incrementing_increment,
                wait_exponential_multiplier=wait_exponential_multiplier,
                wait_exponential_max=wait_exponential_max,
                retry_on_exception=retry_on_exception,
                retry_on_result=retry_on_result
            ).call(f, *args, **kw)
        return wrapped_f
    return wrap


class Retrying:

    def __init__(self,
                 stop='never_stop', stop_max_attempt_number=5, stop_max_delay=100,
                 wait='no_sleep',
                 wait_fixed=1000,
                 wait_random_min=0, wait_random_max=1000,
                 wait_incrementing_start=0, wait_incrementing_increment=100,
                 wait_exponential_multiplier=1, wait_exponential_max=sys.maxint,
                 retry_on_exception=None,
                 retry_on_result=None):

        # stop behavior
        self.stop = getattr(self, stop)
        self._stop_max_attempt_number = stop_max_attempt_number
        self._stop_max_delay = stop_max_delay

        # wait behavior
        self.wait = getattr(self, wait)
        self._wait_fixed = wait_fixed
        self._wait_random_min = wait_random_min
        self._wait_random_max = wait_random_max
        self._wait_incrementing_start = wait_incrementing_start
        self._wait_incrementing_increment = wait_incrementing_increment
        self._wait_exponential_multiplier = wait_exponential_multiplier
        self._wait_exponential_max = wait_exponential_max

        # retry on exception filter
        if retry_on_exception is None:
            self._retry_on_exception = self.never_reject
        else:
            self._retry_on_exception = retry_on_exception

        # retry on result filter
        if retry_on_result is None:
            self._retry_on_result = self.never_reject
        else:
            self._retry_on_result = retry_on_result

    def never_stop(self, previous_attempt_number, delay_since_first_attempt_ms):
        return False

    def stop_after_attempt(self, previous_attempt_number, delay_since_first_attempt_ms):
        return previous_attempt_number >= self._stop_max_attempt_number

    def stop_after_delay(self, previous_attempt_number, delay_since_first_attempt_ms):
        return delay_since_first_attempt_ms >= self._stop_max_delay

    def no_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        return 0

    def fixed_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        return self._wait_fixed

    def random_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        return random.randint(self._wait_random_min, self._wait_random_max)

    def incrementing_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        result = self._wait_incrementing_start + (self._wait_incrementing_increment * (previous_attempt_number - 1))
        if result < 0:
            result = 0
        return result

    def exponential_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        exp = 2 ** previous_attempt_number
        result = self._wait_exponential_multiplier * exp
        if result > self._wait_exponential_max:
            result = self._wait_exponential_max
        if result < 0:
            result = 0
        return result

    def never_reject(self, result):
        return False

    def should_reject(self, attempt):
        reject = False
        if attempt.has_exception:
            reject |= self._retry_on_exception(attempt.value)
        else:
            reject |= self._retry_on_result(attempt.value)

        return reject

    def call(self, fn, *args, **kwargs):
        start_time = int(round(time.time() * 1000))
        attempt_number = 1
        while True:
            try:
                attempt = Attempt(fn(*args, **kwargs), False)
            except BaseException as e:
                attempt = Attempt(e, True)

            if not self.should_reject(attempt):
                return attempt.get()

            delay_since_first_attempt_ms = int(round(time.time() * 1000)) - start_time
            if self.stop(attempt_number, delay_since_first_attempt_ms):
                raise RetryError(attempt_number, attempt)
            else:
                sleep = self.wait(attempt_number, delay_since_first_attempt_ms)
                time.sleep(sleep / 1000.0)

            attempt_number += 1

class Attempt:

    def __init__(self, value, has_exception):
        self.value = value
        self.has_exception = has_exception

    def get(self):
        if self.has_exception:
            raise self.value
        else:
            return self.value

class RetryError(Exception):

    def __init__(self, failed_attempts, last_attempt):
        self.failed_attempts = failed_attempts
        self.last_attempt = last_attempt

    def __str__(self):
        return "Failed attempts: %s, Last attempt: %s" % (str(self.failed_attempts), str(self.last_attempt))