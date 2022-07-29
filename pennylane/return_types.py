# Copyright 2022 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Class and functions for activating, deactivating and checking the new return types system
"""
# pylint: disable=too-few-public-methods


class ReturnType:
    """Class to store the attribute `activated` which indicates if the new return type system is on. Default=False."""

    activated = False


def enable_return():
    """Function that turns on the new return type system."""
    ReturnType.activated = True


def disable_return():
    """Function that turns off the new return type system."""
    ReturnType.activated = False


def active_return():
    """Function that returns if the new return types system is activated."""
    return ReturnType.activated
