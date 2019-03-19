# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import mock
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import utils
import pcmk


def write_file(path, content, *args, **kwargs):
    with open(path, 'w') as f:
        f.write(content)
        f.flush()


@mock.patch.object(utils, 'log', lambda *args, **kwargs: None)
@mock.patch.object(utils, 'write_file', write_file)
class UtilsTestCaseWriteTmp(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        utils.COROSYNC_CONF = os.path.join(self.tmpdir, 'corosync.conf')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @mock.patch.object(utils, 'get_ha_nodes', lambda *args: {'1': '10.0.0.1'})
    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    @mock.patch.object(utils, 'get_network_address')
    @mock.patch.object(utils, 'config')
    def check_debug(self, enabled, mock_config, get_network_address,
                    relation_ids, related_units, relation_get):
        cfg = {'debug': enabled,
               'prefer-ipv6': False,
               'corosync_mcastport': '1234',
               'corosync_transport': 'udpu',
               'corosync_mcastaddr': 'corosync_mcastaddr'}

        def c(k):
            return cfg.get(k)

        mock_config.side_effect = c
        get_network_address.return_value = "127.0.0.1"
        relation_ids.return_value = ['foo:1']
        related_units.return_value = ['unit-machine-0']
        relation_get.return_value = 'iface'

        conf = utils.get_corosync_conf()

        if enabled:
            self.assertEqual(conf['debug'], enabled)
        else:
            self.assertFalse('debug' in conf)

        self.assertTrue(utils.emit_corosync_conf())

        with open(utils.COROSYNC_CONF) as fd:
            content = fd.read()
            if enabled:
                pattern = 'debug: on\n'
            else:
                pattern = 'debug: off\n'

            matches = re.findall(pattern, content, re.M)
            self.assertEqual(len(matches), 2, str(matches))

    def test_debug_on(self):
        self.check_debug(True)

    def test_debug_off(self):
        self.check_debug(False)


class UtilsTestCase(unittest.TestCase):

    @mock.patch.object(utils, 'config')
    def test_get_transport(self, mock_config):
        mock_config.return_value = 'udp'
        self.assertEqual('udp', utils.get_transport())

        mock_config.return_value = 'udpu'
        self.assertEqual('udpu', utils.get_transport())

        mock_config.return_value = 'hafu'
        self.assertRaises(ValueError, utils.get_transport)

    def test_nulls(self):
        self.assertEqual(utils.nulls({'a': '', 'b': None, 'c': False}),
                         ['a', 'b'])

    @mock.patch.object(utils, 'local_unit', lambda *args: 'hanode/0')
    @mock.patch.object(utils, 'get_ipv6_addr')
    @mock.patch.object(utils, 'get_host_ip')
    @mock.patch.object(utils.utils, 'is_ipv6', lambda *args: None)
    @mock.patch.object(utils, 'get_corosync_id', lambda u: "%s-cid" % (u))
    @mock.patch.object(utils, 'peer_ips', lambda *args, **kwargs:
                       {'hanode/1': '10.0.0.2'})
    @mock.patch.object(utils, 'unit_get')
    @mock.patch.object(utils, 'config')
    def test_get_ha_nodes(self, mock_config, mock_unit_get, mock_get_host_ip,
                          mock_get_ipv6_addr):
        mock_get_host_ip.side_effect = lambda host: host

        def unit_get(key):
            return {'private-address': '10.0.0.1'}.get(key)

        mock_unit_get.side_effect = unit_get

        def config(key):
            return {'prefer-ipv6': False}.get(key)

        mock_config.side_effect = config
        nodes = utils.get_ha_nodes()
        self.assertEqual(nodes, {'hanode/0-cid': '10.0.0.1',
                                 'hanode/1-cid': '10.0.0.2'})

        self.assertTrue(mock_get_host_ip.called)
        self.assertFalse(mock_get_ipv6_addr.called)

    @mock.patch.object(utils, 'local_unit', lambda *args: 'hanode/0')
    @mock.patch.object(utils, 'get_ipv6_addr')
    @mock.patch.object(utils, 'get_host_ip')
    @mock.patch.object(utils.utils, 'is_ipv6')
    @mock.patch.object(utils, 'get_corosync_id', lambda u: "%s-cid" % (u))
    @mock.patch.object(utils, 'peer_ips', lambda *args, **kwargs:
                       {'hanode/1': '2001:db8:1::2'})
    @mock.patch.object(utils, 'unit_get')
    @mock.patch.object(utils, 'config')
    def test_get_ha_nodes_ipv6(self, mock_config, mock_unit_get, mock_is_ipv6,
                               mock_get_host_ip, mock_get_ipv6_addr):
        mock_get_ipv6_addr.return_value = '2001:db8:1::1'
        mock_get_host_ip.side_effect = lambda host: host

        def unit_get(key):
            return {'private-address': '10.0.0.1'}.get(key)

        mock_unit_get.side_effect = unit_get

        def config(key):
            return {'prefer-ipv6': True}.get(key)

        mock_config.side_effect = config
        nodes = utils.get_ha_nodes()
        self.assertEqual(nodes, {'hanode/0-cid': '2001:db8:1::1',
                                 'hanode/1-cid': '2001:db8:1::2'})

        self.assertFalse(mock_get_host_ip.called)
        self.assertTrue(mock_get_ipv6_addr.called)

    @mock.patch.object(utils, 'assert_charm_supports_dns_ha')
    @mock.patch.object(utils, 'config')
    def test_validate_dns_ha_valid(self, config,
                                   assert_charm_supports_dns_ha):
        cfg = {'maas_url': 'http://maas/MAAAS/',
               'maas_credentials': 'secret'}
        config.side_effect = lambda key: cfg.get(key)

        self.assertTrue(utils.validate_dns_ha())
        self.assertTrue(assert_charm_supports_dns_ha.called)

    @mock.patch.object(utils, 'assert_charm_supports_dns_ha')
    @mock.patch.object(utils, 'status_set')
    @mock.patch.object(utils, 'config')
    def test_validate_dns_ha_invalid(self, config, status_set,
                                     assert_charm_supports_dns_ha):
        cfg = {'maas_url': 'http://maas/MAAAS/',
               'maas_credentials': None}
        config.side_effect = lambda key: cfg.get(key)

        self.assertRaises(utils.MAASConfigIncomplete,
                          lambda: utils.validate_dns_ha())
        self.assertTrue(assert_charm_supports_dns_ha.called)
        status_set.assert_not_called()

    @mock.patch.object(utils, 'apt_install')
    @mock.patch.object(utils, 'apt_update')
    @mock.patch.object(utils, 'add_source')
    @mock.patch.object(utils, 'config')
    def test_setup_maas_api(self, config, add_source, apt_update, apt_install):
        cfg = {'maas_source': 'ppa:maas/stable'}
        config.side_effect = lambda key: cfg.get(key)

        utils.setup_maas_api()
        add_source.assert_called_with(cfg['maas_source'])
        self.assertTrue(apt_install.called)

    @mock.patch('os.path.isfile')
    def test_ocf_file_exists(self, isfile_mock):
        RES_NAME = 'res_ceilometer_agent_central'
        resources = {RES_NAME: ('ocf:openstack:ceilometer-agent-central')}
        utils.ocf_file_exists(RES_NAME, resources)
        wish = '/usr/lib/ocf/resource.d/openstack/ceilometer-agent-central'
        isfile_mock.assert_called_once_with(wish)

    @mock.patch.object(subprocess, 'check_output')
    @mock.patch.object(subprocess, 'call')
    def test_kill_legacy_ocf_daemon_process(self, call_mock,
                                            check_output_mock):
        ps_output = '''
          PID CMD
          6863 sshd: ubuntu@pts/7
          11109 /usr/bin/python /usr/bin/ceilometer-agent-central --config
        '''
        check_output_mock.return_value = ps_output
        utils.kill_legacy_ocf_daemon_process('res_ceilometer_agent_central')
        call_mock.assert_called_once_with(['sudo', 'kill', '-9', '11109'])

    @mock.patch.object(pcmk, 'wait_for_pcmk')
    def test_try_pcmk_wait(self, mock_wait_for_pcmk):
        # Returns OK
        mock_wait_for_pcmk.side_effect = None
        self.assertEqual(None, utils.try_pcmk_wait())

        # Raises Exception
        mock_wait_for_pcmk.side_effect = pcmk.ServicesNotUp
        with self.assertRaises(pcmk.ServicesNotUp):
            utils.try_pcmk_wait()

    @mock.patch.object(pcmk, 'wait_for_pcmk')
    @mock.patch.object(utils, 'service_running')
    def test_services_running(self, mock_service_running,
                              mock_wait_for_pcmk):
        # OS not running
        mock_service_running.return_value = False
        self.assertFalse(utils.services_running())

        # Functional not running
        mock_service_running.return_value = True
        mock_wait_for_pcmk.side_effect = pcmk.ServicesNotUp
        with self.assertRaises(pcmk.ServicesNotUp):
            utils.services_running()

        # All running
        mock_service_running.return_value = True
        mock_wait_for_pcmk.side_effect = None
        mock_wait_for_pcmk.return_value = True
        self.assertTrue(utils.services_running())

    @mock.patch.object(pcmk, 'wait_for_pcmk')
    @mock.patch.object(utils, 'restart_corosync')
    def test_validated_restart_corosync(self, mock_restart_corosync,
                                        mock_wait_for_pcmk):
        # Services are down
        mock_restart_corosync.mock_calls = []
        mock_restart_corosync.return_value = False
        with self.assertRaises(pcmk.ServicesNotUp):
            utils.validated_restart_corosync(retries=3)
        self.assertEqual(3, len(mock_restart_corosync.mock_calls))

        # Services are up
        mock_restart_corosync.mock_calls = []
        mock_restart_corosync.return_value = True
        utils.validated_restart_corosync(retries=10)
        self.assertEqual(1, len(mock_restart_corosync.mock_calls))

    @mock.patch.object(utils, 'is_unit_paused_set')
    @mock.patch.object(utils, 'services_running')
    @mock.patch.object(utils, 'service_start')
    @mock.patch.object(utils, 'service_stop')
    @mock.patch.object(utils, 'service_running')
    def test_restart_corosync(self, mock_service_running,
                              mock_service_stop, mock_service_start,
                              mock_services_running, mock_is_unit_paused_set):
        # PM up, services down
        mock_service_running.return_value = True
        mock_is_unit_paused_set.return_value = False
        mock_services_running.return_value = False
        self.assertFalse(utils.restart_corosync())
        mock_service_stop.assert_has_calls([mock.call('pacemaker'),
                                            mock.call('corosync')])
        mock_service_start.assert_has_calls([mock.call('corosync'),
                                            mock.call('pacemaker')])

        # PM already down, services down
        mock_service_running.return_value = False
        mock_is_unit_paused_set.return_value = False
        mock_services_running.return_value = False
        self.assertFalse(utils.restart_corosync())
        mock_service_stop.assert_has_calls([mock.call('corosync')])
        mock_service_start.assert_has_calls([mock.call('corosync'),
                                            mock.call('pacemaker')])

        # PM already down, services up
        mock_service_running.return_value = True
        mock_is_unit_paused_set.return_value = False
        mock_services_running.return_value = True
        self.assertTrue(utils.restart_corosync())
        mock_service_stop.assert_has_calls([mock.call('pacemaker'),
                                            mock.call('corosync')])
        mock_service_start.assert_has_calls([mock.call('corosync'),
                                            mock.call('pacemaker')])

    @mock.patch.object(subprocess, 'check_call')
    @mock.patch.object(utils.os, 'mkdir')
    @mock.patch.object(utils.os.path, 'exists')
    @mock.patch.object(utils, 'render_template')
    @mock.patch.object(utils, 'write_file')
    @mock.patch.object(utils, 'is_unit_paused_set')
    @mock.patch.object(utils, 'config')
    def test_emit_systemd_overrides_file(self, mock_config,
                                         mock_is_unit_paused_set,
                                         mock_write_file, mock_render_template,
                                         mock_path_exists,
                                         mock_mkdir, mock_check_call):

        # Normal values
        cfg = {'service_stop_timeout': 30,
               'service_start_timeout': 90}
        mock_config.side_effect = lambda key: cfg.get(key)

        mock_is_unit_paused_set.return_value = True
        mock_path_exists.return_value = True
        utils.emit_systemd_overrides_file()
        self.assertEqual(2, len(mock_write_file.mock_calls))
        mock_render_template.assert_has_calls(
            [mock.call('systemd-overrides.conf', cfg),
             mock.call('systemd-overrides.conf', cfg)])
        mock_check_call.assert_has_calls([mock.call(['systemctl',
                                                     'daemon-reload'])])
        mock_write_file.mock_calls = []
        mock_render_template.mock_calls = []
        mock_check_call.mock_calls = []

        # Disable timeout
        cfg = {'service_stop_timeout': -1,
               'service_start_timeout': -1}
        expected_cfg = {'service_stop_timeout': 'infinity',
                        'service_start_timeout': 'infinity'}
        mock_config.side_effect = lambda key: cfg.get(key)
        mock_is_unit_paused_set.return_value = True
        mock_path_exists.return_value = True
        utils.emit_systemd_overrides_file()
        self.assertEqual(2, len(mock_write_file.mock_calls))
        mock_render_template.assert_has_calls(
            [mock.call('systemd-overrides.conf', expected_cfg),
             mock.call('systemd-overrides.conf', expected_cfg)])
        mock_check_call.assert_has_calls([mock.call(['systemctl',
                                                     'daemon-reload'])])

    @mock.patch('pcmk.set_property')
    @mock.patch('pcmk.get_property')
    def test_maintenance_mode(self, mock_get_property, mock_set_property):
        # enable maintenance-mode
        mock_get_property.return_value = 'false\n'
        utils.maintenance_mode(True)
        mock_get_property.assert_called_with('maintenance-mode')
        mock_set_property.assert_called_with('maintenance-mode', 'true')
        mock_get_property.reset_mock()
        mock_set_property.reset_mock()
        mock_get_property.return_value = 'true\n'
        utils.maintenance_mode(True)
        mock_get_property.assert_called_with('maintenance-mode')
        mock_set_property.assert_not_called()

        # disable maintenance-mode
        mock_get_property.return_value = 'true\n'
        utils.maintenance_mode(False)
        mock_get_property.assert_called_with('maintenance-mode')
        mock_set_property.assert_called_with('maintenance-mode', 'false')
        mock_get_property.reset_mock()
        mock_set_property.reset_mock()
        mock_get_property.return_value = 'false\n'
        utils.maintenance_mode(False)
        mock_get_property.assert_called_with('maintenance-mode')
        mock_set_property.assert_not_called()

    @mock.patch('subprocess.check_call')
    def test_needs_maas_dns_migration(self, check_call):
        ret = utils.needs_maas_dns_migration()
        self.assertEqual(True, ret)

        check_call.side_effect = subprocess.CalledProcessError(1, '')
        ret = utils.needs_maas_dns_migration()
        self.assertEqual(False, ret)

    def test_get_ip_addr_from_resource_params(self):
        param_str = 'params fqdn="keystone.maas" ip_address="{}" '
        for addr in ("172.16.0.4", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"):
            ip = utils.get_ip_addr_from_resource_params(param_str.format(addr))
            self.assertEqual(addr, ip)

        ip = utils.get_ip_addr_from_resource_params("no_ip_addr")
        self.assertEqual(None, ip)

    @mock.patch.object(utils, 'write_file')
    @mock.patch.object(utils, 'mkdir')
    def test_write_maas_dns_address(self, mkdir, write_file):
        utils.write_maas_dns_address("res_keystone_public_hostname",
                                     "172.16.0.1")
        mkdir.assert_called_once_with("/etc/maas_dns")
        write_file.assert_called_once_with(
            "/etc/maas_dns/res_keystone_public_hostname", content="172.16.0.1")

    @mock.patch.object(utils, 'relation_get')
    def test_parse_data_legacy(self, relation_get):
        _rel_data = {
            'testkey': repr({'test': 1})
        }
        relation_get.side_effect = lambda key, relid, unit: _rel_data.get(key)
        self.assertEqual(utils.parse_data('hacluster:1',
                                          'neutron-api/0',
                                          'testkey'),
                         {'test': 1})
        relation_get.assert_has_calls([
            mock.call('json_testkey', 'neutron-api/0', 'hacluster:1'),
            mock.call('testkey', 'neutron-api/0', 'hacluster:1'),
        ])

    @mock.patch.object(utils, 'relation_get')
    def test_parse_data_json(self, relation_get):
        _rel_data = {
            'json_testkey': json.dumps({'test': 1}),
            'testkey': repr({'test': 1})
        }
        relation_get.side_effect = lambda key, relid, unit: _rel_data.get(key)
        self.assertEqual(utils.parse_data('hacluster:1',
                                          'neutron-api/0',
                                          'testkey'),
                         {'test': 1})
        # NOTE(jamespage): as json is the preferred format, the call for
        #                  testkey should not occur.
        relation_get.assert_has_calls([
            mock.call('json_testkey', 'neutron-api/0', 'hacluster:1'),
        ])

    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    def test_get_resources_on_remotes_all_false(self, relation_ids,
                                                related_units, relation_get):
        rdata = {
            'pacemaker-remote:49': {
                'pacemaker-remote/0': {'enable-resources': "false"},
                'pacemaker-remote/1': {'enable-resources': "false"},
                'pacemaker-remote/2': {'enable-resources': "false"}}}

        relation_ids.side_effect = lambda x: rdata.keys()
        related_units.side_effect = lambda x: rdata[x].keys()
        relation_get.side_effect = lambda x, y, z: rdata[z][y].get(x)
        self.assertFalse(utils.get_resources_on_remotes())

    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    def test_get_resources_on_remotes_all_true(self, relation_ids,
                                               related_units,
                                               relation_get):
        rdata = {
            'pacemaker-remote:49': {
                'pacemaker-remote/0': {'enable-resources': "true"},
                'pacemaker-remote/1': {'enable-resources': "true"},
                'pacemaker-remote/2': {'enable-resources': "true"}}}

        relation_ids.side_effect = lambda x: rdata.keys()
        related_units.side_effect = lambda x: rdata[x].keys()
        relation_get.side_effect = lambda x, y, z: rdata[z][y].get(x)
        self.assertTrue(utils.get_resources_on_remotes())

    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    def test_get_resources_on_remotes_mix(self, relation_ids, related_units,
                                          relation_get):
        rdata = {
            'pacemaker-remote:49': {
                'pacemaker-remote/0': {'enable-resources': "true"},
                'pacemaker-remote/1': {'enable-resources': "false"},
                'pacemaker-remote/2': {'enable-resources': "true"}}}

        relation_ids.side_effect = lambda x: rdata.keys()
        related_units.side_effect = lambda x: rdata[x].keys()
        relation_get.side_effect = lambda x, y, z: rdata[z][y].get(x)
        with self.assertRaises(ValueError):
            self.assertTrue(utils.get_resources_on_remotes())

    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    def test_get_resources_on_remotes_missing(self, relation_ids,
                                              related_units,
                                              relation_get):
        rdata = {
            'pacemaker-remote:49': {
                'pacemaker-remote/0': {},
                'pacemaker-remote/1': {},
                'pacemaker-remote/2': {}}}

        relation_ids.side_effect = lambda x: rdata.keys()
        related_units.side_effect = lambda x: rdata[x].keys()
        relation_get.side_effect = lambda x, y, z: rdata[z][y].get(x, None)
        with self.assertRaises(ValueError):
            self.assertTrue(utils.get_resources_on_remotes())

    @mock.patch.object(utils, 'get_resources_on_remotes')
    @mock.patch('pcmk.commit')
    def test_set_cluster_symmetry_true(self, commit, get_resources_on_remotes):
        get_resources_on_remotes.return_value = True
        utils.set_cluster_symmetry()
        commit.assert_called_once_with(
            'crm configure property symmetric-cluster=true')

    @mock.patch.object(utils, 'get_resources_on_remotes')
    @mock.patch('pcmk.commit')
    def test_set_cluster_symmetry_false(self, commit,
                                        get_resources_on_remotes):
        get_resources_on_remotes.return_value = False
        utils.set_cluster_symmetry()
        commit.assert_called_once_with(
            'crm configure property symmetric-cluster=false')

    @mock.patch.object(utils, 'get_resources_on_remotes')
    @mock.patch('pcmk.commit')
    def test_set_cluster_symmetry_unknown(self, commit,
                                          get_resources_on_remotes):
        get_resources_on_remotes.side_effect = ValueError()
        utils.set_cluster_symmetry()
        self.assertFalse(commit.called)

    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.crm_opt_exists')
    @mock.patch('pcmk.list_nodes')
    def test_add_location_rules_for_local_nodes(self, list_nodes,
                                                crm_opt_exists, commit):
        existing_resources = ['loc-res1-node1']
        list_nodes.return_value = ['node1', 'node2']
        crm_opt_exists.side_effect = lambda x: x in existing_resources
        utils.add_location_rules_for_local_nodes('res1')
        commit.assert_called_once_with(
            'crm -w -F configure location loc-res1-node2 res1 0: node2')

    @mock.patch('pcmk.is_resource_present')
    @mock.patch('pcmk.commit')
    def test_configure_pacemaker_remote(self, commit, is_resource_present):
        is_resource_present.return_value = False
        self.assertEqual(
            utils.configure_pacemaker_remote(
                'juju-aa0ba5-zaza-ed2ce6f303f0-10'),
            'juju-aa0ba5-zaza-ed2ce6f303f0-10')
        commit.assert_called_once_with(
            'crm configure primitive juju-aa0ba5-zaza-ed2ce6f303f0-10 '
            'ocf:pacemaker:remote params '
            'server=juju-aa0ba5-zaza-ed2ce6f303f0-10 '
            'reconnect_interval=60 op monitor interval=30s')

    @mock.patch('pcmk.is_resource_present')
    @mock.patch('pcmk.commit')
    def test_configure_pacemaker_remote_fqdn(self, commit,
                                             is_resource_present):
        is_resource_present.return_value = False
        self.assertEqual(
            utils.configure_pacemaker_remote(
                'juju-aa0ba5-zaza-ed2ce6f303f0-10.maas'),
            'juju-aa0ba5-zaza-ed2ce6f303f0-10')
        commit.assert_called_once_with(
            'crm configure primitive juju-aa0ba5-zaza-ed2ce6f303f0-10 '
            'ocf:pacemaker:remote params '
            'server=juju-aa0ba5-zaza-ed2ce6f303f0-10.maas '
            'reconnect_interval=60 op monitor interval=30s')

    @mock.patch('pcmk.is_resource_present')
    @mock.patch('pcmk.commit')
    def test_configure_pacemaker_remote_duplicate(self, commit,
                                                  is_resource_present):
        is_resource_present.return_value = True
        self.assertEqual(
            utils.configure_pacemaker_remote(
                'juju-aa0ba5-zaza-ed2ce6f303f0-10.maas'),
            'juju-aa0ba5-zaza-ed2ce6f303f0-10')
        self.assertFalse(commit.called)

    @mock.patch('pcmk.commit')
    def test_cleanup_remote_nodes(self, commit):
        utils.cleanup_remote_nodes(['res-node1', 'res-node2'])
        commit_calls = [
            mock.call('crm resource cleanup res-node1'),
            mock.call('crm resource cleanup res-node2')]
        commit.assert_has_calls(commit_calls)

    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    @mock.patch.object(utils, 'add_location_rules_for_local_nodes')
    @mock.patch.object(utils, 'configure_pacemaker_remote')
    @mock.patch.object(utils, 'configure_pacemaker_remote_stonith')
    @mock.patch.object(utils, 'cleanup_remote_nodes')
    def test_configure_pacemaker_remotes(self,
                                         cleanup_remote_nodes,
                                         configure_pacemaker_remote_stonith,
                                         configure_pacemaker_remote,
                                         add_location_rules_for_local_nodes,
                                         relation_ids, related_units,
                                         relation_get):
        rdata = {
            'pacemaker-remote:49': {
                'pacemaker-remote/0': {
                    'remote-hostname': '"node1"',
                    'stonith-hostname': '"st-node1"'},
                'pacemaker-remote/1': {
                    'remote-hostname': '"node2"'},
                'pacemaker-remote/2': {
                    'stonith-hostname': '"st-node3"'}}}
        relation_ids.side_effect = lambda x: rdata.keys()
        related_units.side_effect = lambda x: rdata[x].keys()
        relation_get.side_effect = lambda x, y, z: rdata[z][y].get(x, None)
        configure_pacemaker_remote.side_effect = lambda x: 'res-{}'.format(x)
        utils.configure_pacemaker_remotes()
        remote_calls = [
            mock.call('node1'),
            mock.call('node2')]
        add_loc_calls = [
            mock.call('res-node1'),
            mock.call('res-node2')]
        stonith_calls = [
            mock.call('st-node1'),
            mock.call('st-node3')]
        configure_pacemaker_remote.assert_has_calls(
            remote_calls,
            any_order=True)
        add_location_rules_for_local_nodes.assert_has_calls(
            add_loc_calls,
            any_order=True)
        configure_pacemaker_remote_stonith.assert_has_calls(
            stonith_calls,
            any_order=True)
        cleanup_remote_nodes.assert_called_once_with(
            ['res-node2', 'res-node1'])

    @mock.patch.object(utils, 'config')
    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.is_resource_present')
    def test_configure_pacemaker_remote_stonith(self, is_resource_present,
                                                commit, config):
        cfg = {
            'maas_url': 'http://maas/2.0',
            'maas_credentials': 'apikey'}
        is_resource_present.return_value = False
        config.side_effect = lambda x: cfg.get(x)
        utils.configure_pacemaker_remote_stonith('node1')
        cmd = (
            "crm configure primitive st-node1 "
            "stonith:external/maas "
            "params url='http://maas/2.0' apikey='apikey' "
            "hostnames=node1 "
            "op monitor interval=25 start-delay=25 "
            "timeout=25")
        commit_calls = [
            mock.call(cmd),
            mock.call('crm configure property stonith-enabled=true'),
        ]
        commit.assert_has_calls(commit_calls)

    @mock.patch.object(utils, 'config')
    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.is_resource_present')
    def test_configure_pacemaker_remote_stonith_duplicate(self,
                                                          is_resource_present,
                                                          commit, config):
        cfg = {
            'maas_url': 'http://maas/2.0',
            'maas_credentials': 'apikey'}
        is_resource_present.return_value = True
        config.side_effect = lambda x: cfg.get(x)
        utils.configure_pacemaker_remote_stonith('node1')
        self.assertFalse(commit.called)

    @mock.patch.object(utils, 'config')
    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.is_resource_present')
    def test_configure_pacemaker_remote_stonith_no_url(self,
                                                       is_resource_present,
                                                       commit, config):
        cfg = {
            'maas_credentials': 'apikey'}
        is_resource_present.return_value = False
        config.side_effect = lambda x: cfg.get(x)
        with self.assertRaises(Exception):
            utils.configure_pacemaker_remote_stonith('node1')

    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.list_nodes')
    @mock.patch.object(utils, 'add_location_rules_for_local_nodes')
    @mock.patch.object(utils, 'get_resources_on_remotes')
    def test_configure_resources_on_remotes(self, get_resources_on_remotes,
                                            add_location_rules_for_local_nodes,
                                            list_nodes, commit):
        list_nodes.return_value = ['node1', 'node2', 'node3']
        get_resources_on_remotes.return_value = False
        clones = {
            'cl_res_masakari_haproxy': u'res_masakari_haproxy'}
        resources = {
            'res_masakari_1e39e82_vip': u'ocf:heartbeat:IPaddr2',
            'res_masakari_flump': u'ocf:heartbeat:IPaddr2',
            'res_masakari_haproxy': u'lsb:haproxy'}
        groups = {
            'grp_masakari_vips': 'res_masakari_1e39e82_vip'}
        utils.configure_resources_on_remotes(
            resources=resources,
            clones=clones,
            groups=groups)
        add_loc_calls = [
            mock.call('cl_res_masakari_haproxy'),
            mock.call('res_masakari_flump'),
            mock.call('grp_masakari_vips')]
        add_location_rules_for_local_nodes.assert_has_calls(
            add_loc_calls,
            any_order=True)
        commit.assert_called_once_with(
            'crm_resource --resource cl_res_masakari_haproxy '
            '--set-parameter clone-max '
            '--meta --parameter-value 3')

    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.list_nodes')
    @mock.patch.object(utils, 'add_location_rules_for_local_nodes')
    @mock.patch.object(utils, 'get_resources_on_remotes')
    def test_configure_resources_on_remotes_true(
            self,
            get_resources_on_remotes,
            add_location_rules_for_local_nodes,
            list_nodes,
            commit):
        list_nodes.return_value = ['node1', 'node2', 'node3']
        get_resources_on_remotes.return_value = True
        clones = {
            'cl_res_masakari_haproxy': u'res_masakari_haproxy'}
        resources = {
            'res_masakari_1e39e82_vip': u'ocf:heartbeat:IPaddr2',
            'res_masakari_flump': u'ocf:heartbeat:IPaddr2',
            'res_masakari_haproxy': u'lsb:haproxy'}
        groups = {
            'grp_masakari_vips': 'res_masakari_1e39e82_vip'}
        utils.configure_resources_on_remotes(
            resources=resources,
            clones=clones,
            groups=groups)
        self.assertFalse(commit.called)

    @mock.patch('pcmk.commit')
    @mock.patch('pcmk.list_nodes')
    @mock.patch.object(utils, 'add_location_rules_for_local_nodes')
    @mock.patch.object(utils, 'get_resources_on_remotes')
    def test_configure_resources_on_remotes_unknown(
            self,
            get_resources_on_remotes,
            add_location_rules_for_local_nodes,
            list_nodes,
            commit):
        list_nodes.return_value = ['node1', 'node2', 'node3']
        get_resources_on_remotes.side_effect = ValueError
        clones = {
            'cl_res_masakari_haproxy': u'res_masakari_haproxy'}
        resources = {
            'res_masakari_1e39e82_vip': u'ocf:heartbeat:IPaddr2',
            'res_masakari_flump': u'ocf:heartbeat:IPaddr2',
            'res_masakari_haproxy': u'lsb:haproxy'}
        groups = {
            'grp_masakari_vips': 'res_masakari_1e39e82_vip'}
        utils.configure_resources_on_remotes(
            resources=resources,
            clones=clones,
            groups=groups)
        self.assertFalse(commit.called)
