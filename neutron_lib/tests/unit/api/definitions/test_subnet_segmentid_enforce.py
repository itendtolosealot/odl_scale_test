# Copyright 2018 AT&T Corporation.
# All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron_lib.api.definitions import segment
from neutron_lib.api.definitions import subnet_segmentid_enforce
from neutron_lib.tests.unit.api.definitions import base


class SubnetSegmentIDEnforceDefinitionTestCase(base.DefinitionBaseTestCase):
    extension_module = subnet_segmentid_enforce
    extension_attributes = (segment.SEGMENT_ID,)
