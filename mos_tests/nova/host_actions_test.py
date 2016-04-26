#    Copyright 2016 Mirantis, Inc.
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

import pytest

from mos_tests.functions import common
from mos_tests.functions import network_checks
from mos_tests.functions import os_cli

pytestmark = pytest.mark.undestructive


@pytest.fixture
def nova_client(controller_remote):
    return os_cli.Nova(controller_remote)


@pytest.mark.check_env_('has_2_or_more_computes')
@pytest.mark.testrail_id('842499')
def test_live_evacuate_instances(instances, os_conn, env, keypair,
                                 nova_client):
    """Live evacuate all instances of the specified host to other available
    hosts without shared storage

    Scenario:
        1. Create net01, net01__subnet
        2. Boot instances vm1 and vm2 in net01 on compute node1
        3. Run the 'nova host-evacuate-live' command to live-migrate
            vm1 and vm2 instances from compute node1 to compute node2:
            nova host-evacuate-live --target-host node-2.domain.tld \
            --block-migrate node-1.domain.tld
        4. Check that all live-migrated instances are hosted on target host
            and are in ACTIVE status
        5. Check pings between vm1 and vm2
    """
    old_host = getattr(instances[0], 'OS-EXT-SRV-ATTR:host')
    new_host = [x.hypervisor_hostname
                for x in os_conn.nova.hypervisors.list()
                if x.hypervisor_hostname != old_host][0]

    nova_client(
        'host-evacuate-live',
        params='--target-host {new_host} --block-migrate {old_host}'.format(
            old_host=old_host,
            new_host=new_host))

    common.wait(lambda: all([os_conn.is_server_active(x) for x in instances]),
                timeout_seconds=2 * 60,
                waiting_for='instances became to ACTIVE status')

    for instance in instances:
        instance.get()
        assert getattr(instance, 'OS-EXT-SRV-ATTR:host') == new_host

    for instance1, instance2 in zip(instances, instances[::-1]):
        ip = os_conn.get_nova_instance_ips(instance2)['fixed']
        network_checks.check_ping_from_vm(env,
                                          os_conn,
                                          instance1,
                                          vm_keypair=keypair,
                                          ip_to_ping=ip)