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

import mock
import pcmk
import os
import tempfile
import unittest
from distutils.version import StrictVersion


CRM_CONFIGURE_SHOW_XML = '''<?xml version="1.0" ?>
<cib num_updates="1" dc-uuid="1002" update-origin="juju-34fde5-0" crm_feature_set="3.0.7" validate-with="pacemaker-1.2" update-client="cibadmin" epoch="1103" admin_epoch="0" cib-last-written="Fri Aug  4 13:45:06 2017" have-quorum="1">
  <configuration>
    <crm_config>
      <cluster_property_set id="cib-bootstrap-options">
        <nvpair id="cib-bootstrap-options-dc-version" name="dc-version" value="1.1.10-42f2063"/>
        <nvpair id="cib-bootstrap-options-cluster-infrastructure" name="cluster-infrastructure" value="corosync"/>
        <nvpair name="no-quorum-policy" value="stop" id="cib-bootstrap-options-no-quorum-policy"/>
        <nvpair name="stonith-enabled" value="false" id="cib-bootstrap-options-stonith-enabled"/>
      </cluster_property_set>
    </crm_config>
    <nodes>
      <node id="1002" uname="juju-34fde5-0"/>
    </nodes>
    <resources/>
    <constraints/>
    <rsc_defaults>
      <meta_attributes id="rsc-options">
        <nvpair name="resource-stickiness" value="100" id="rsc-options-resource-stickiness"/>
      </meta_attributes>
    </rsc_defaults>
  </configuration>
</cib>

'''  # noqa

CRM_CONFIGURE_SHOW_XML_MAINT_MODE_TRUE = '''<?xml version="1.0" ?>
<cib num_updates="1" dc-uuid="1002" update-origin="juju-34fde5-0" crm_feature_set="3.0.7" validate-with="pacemaker-1.2" update-client="cibadmin" epoch="1103" admin_epoch="0" cib-last-written="Fri Aug  4 13:45:06 2017" have-quorum="1">
  <configuration>
    <crm_config>
      <cluster_property_set id="cib-bootstrap-options">
        <nvpair id="cib-bootstrap-options-dc-version" name="dc-version" value="1.1.10-42f2063"/>
        <nvpair id="cib-bootstrap-options-cluster-infrastructure" name="cluster-infrastructure" value="corosync"/>
        <nvpair name="no-quorum-policy" value="stop" id="cib-bootstrap-options-no-quorum-policy"/>
        <nvpair name="stonith-enabled" value="false" id="cib-bootstrap-options-stonith-enabled"/>
        <nvpair name="maintenance-mode" value="true" id="cib-bootstrap-options-maintenance-mode"/>
      </cluster_property_set>
    </crm_config>
    <nodes>
      <node id="1002" uname="juju-34fde5-0"/>
    </nodes>
    <resources/>
    <constraints/>
    <rsc_defaults>
      <meta_attributes id="rsc-options">
        <nvpair name="resource-stickiness" value="100" id="rsc-options-resource-stickiness"/>
      </meta_attributes>
    </rsc_defaults>
  </configuration>
</cib>

'''  # noqa

CRM_CONFIGURE_SHOW_XML_OPT_EXISTS = '''<?xml version="1.0" ?>
<cib num_updates="30" dc-uuid="1000" update-origin="juju-3a5deb-radosgw-5" crm_feature_set="3.0.10" validate-with="pacemaker-2.4" update-client="crmd" epoch="32" admin_epoch="0" update-user="hacluster" cib-last-written="Tue Sep  4 01:09:37 2018" have-quorum="1">
  <configuration>
    <crm_config>
      <cluster_property_set id="cib-bootstrap-options">
        <nvpair id="cib-bootstrap-options-have-watchdog" name="have-watchdog" value="false"/>
        <nvpair id="cib-bootstrap-options-dc-version" name="dc-version" value="1.1.14-70404b0"/>
        <nvpair id="cib-bootstrap-options-cluster-infrastructure" name="cluster-infrastructure" value="corosync"/>
        <nvpair id="cib-bootstrap-options-cluster-name" name="cluster-name" value="debian"/>
        <nvpair name="no-quorum-policy" value="stop" id="cib-bootstrap-options-no-quorum-policy"/>
        <nvpair name="stonith-enabled" value="false" id="cib-bootstrap-options-stonith-enabled"/>
        <nvpair id="cib-bootstrap-options-last-lrm-refresh" name="last-lrm-refresh" value="1536023377"/>
      </cluster_property_set>
    </crm_config>
    <nodes>
      <node id="1002" uname="juju-3a5deb-radosgw-5"/>
      <node id="1000" uname="juju-3a5deb-radosgw-4"/>
      <node id="1001" uname="juju-3a5deb-radosgw-6"/>
    </nodes>
    <resources>
      <group id="grp_ceph-radosgw_hostnames">
        <primitive id="res_ceph-radosgw_admin_hostname" class="ocf" provider="maas" type="dns">
          <instance_attributes id="res_ceph-radosgw_admin_hostname-instance_attributes">
            <nvpair name="fqdn" value="rgw-public.maas" id="res_ceph-radosgw_admin_hostname-instance_attributes-fqdn"/>
            <nvpair name="ip_address" value="10.5.0.8" id="res_ceph-radosgw_admin_hostname-instance_attributes-ip_address"/>
            <nvpair name="maas_url" value="http://localhost/MAAS" id="res_ceph-radosgw_admin_hostname-instance_attributes-maas_url"/>
            <nvpair name="maas_credentials" value="ubuntu" id="res_ceph-radosgw_admin_hostname-instance_attributes-maas_credentials"/>
          </instance_attributes>
        </primitive>
        <primitive id="res_ceph-radosgw_int_hostname" class="ocf" provider="maas" type="dns">
          <instance_attributes id="res_ceph-radosgw_int_hostname-instance_attributes">
            <nvpair name="fqdn" value="rgw-internal.maas" id="res_ceph-radosgw_int_hostname-instance_attributes-fqdn"/>
            <nvpair name="ip_address" value="10.5.0.8" id="res_ceph-radosgw_int_hostname-instance_attributes-ip_address"/>
            <nvpair name="maas_url" value="http://localhost/MAAS" id="res_ceph-radosgw_int_hostname-instance_attributes-maas_url"/>
            <nvpair name="maas_credentials" value="ubuntu" id="res_ceph-radosgw_int_hostname-instance_attributes-maas_credentials"/>
          </instance_attributes>
        </primitive>
        <primitive id="res_ceph-radosgw_public_hostname" class="ocf" provider="maas" type="dns">
          <instance_attributes id="res_ceph-radosgw_public_hostname-instance_attributes">
            <nvpair name="fqdn" value="rgw-public.maas" id="res_ceph-radosgw_public_hostname-instance_attributes-fqdn"/>
            <nvpair name="ip_address" value="10.5.0.8" id="res_ceph-radosgw_public_hostname-instance_attributes-ip_address"/>
            <nvpair name="maas_url" value="http://localhost/MAAS" id="res_ceph-radosgw_public_hostname-instance_attributes-maas_url"/>
            <nvpair name="maas_credentials" value="ubuntu" id="res_ceph-radosgw_public_hostname-instance_attributes-maas_credentials"/>
          </instance_attributes>
        </primitive>
      </group>
      <clone id="cl_cephrg_haproxy">
        <primitive id="res_cephrg_haproxy" class="lsb" type="haproxy">
          <operations>
            <op name="monitor" interval="5s" id="res_cephrg_haproxy-monitor-5s"/>
          </operations>
        </primitive>
      </clone>
    </resources>
    <constraints/>
    <rsc_defaults>
      <meta_attributes id="rsc-options">
        <nvpair name="resource-stickiness" value="100" id="rsc-options-resource-stickiness"/>
      </meta_attributes>
    </rsc_defaults>
  </configuration>
</cib>
'''  # noqa


class TestPcmk(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)

    def tearDown(self):
        os.remove(self.tmpfile.name)

    @mock.patch('commands.getstatusoutput')
    def test_crm_res_running_true(self, getstatusoutput):
        getstatusoutput.return_value = (0, ("resource res_nova_consoleauth is "
                                            "running on: juju-xxx-machine-6"))
        self.assertTrue(pcmk.crm_res_running('res_nova_consoleauth'))

    @mock.patch('commands.getstatusoutput')
    def test_crm_res_running_stopped(self, getstatusoutput):
        getstatusoutput.return_value = (0, ("resource res_nova_consoleauth is "
                                            "NOT running"))
        self.assertFalse(pcmk.crm_res_running('res_nova_consoleauth'))

    @mock.patch('commands.getstatusoutput')
    def test_crm_res_running_undefined(self, getstatusoutput):
        getstatusoutput.return_value = (1, "foobar")
        self.assertFalse(pcmk.crm_res_running('res_nova_consoleauth'))

    @mock.patch('socket.gethostname')
    @mock.patch('commands.getstatusoutput')
    def test_wait_for_pcmk(self, getstatusoutput, gethostname):
        # Pacemaker is down
        gethostname.return_value = 'hanode-1'
        getstatusoutput.return_value = (1, 'Not the hostname')
        with self.assertRaises(pcmk.ServicesNotUp):
            pcmk.wait_for_pcmk(retries=2, sleep=0)

        # Pacemaker is up
        gethostname.return_value = 'hanode-1'
        getstatusoutput.return_value = (0, 'Hosname: hanode-1')
        self.assertTrue(pcmk.wait_for_pcmk(retries=2, sleep=0))

    @mock.patch('subprocess.check_output')
    def test_crm_version(self, mock_check_output):
        # xenial
        mock_check_output.return_value = "crm 2.2.0\n"
        ret = pcmk.crm_version()
        self.assertEqual(StrictVersion('2.2.0'), ret)
        mock_check_output.assert_called_with(['crm', '--version'],
                                             universal_newlines=True)

        # trusty
        mock_check_output.mock_reset()
        mock_check_output.return_value = ("1.2.5 (Build f2f315daf6a5fd7ddea8e5"
                                          "64cd289aa04218427d)\n")
        ret = pcmk.crm_version()
        self.assertEqual(StrictVersion('1.2.5'), ret)
        mock_check_output.assert_called_with(['crm', '--version'],
                                             universal_newlines=True)

    @mock.patch('subprocess.check_output')
    @mock.patch.object(pcmk, 'crm_version')
    def test_get_property(self, mock_crm_version, mock_check_output):
        mock_crm_version.return_value = StrictVersion('2.2.0')  # xenial
        mock_check_output.return_value = 'false\n'
        self.assertEqual('false\n', pcmk.get_property('maintenance-mode'))

        mock_check_output.assert_called_with(['crm', 'configure',
                                              'show-property',
                                              'maintenance-mode'],
                                             universal_newlines=True)

        mock_crm_version.return_value = StrictVersion('2.4.0')
        mock_check_output.reset_mock()
        self.assertEqual('false\n', pcmk.get_property('maintenance-mode'))
        mock_check_output.assert_called_with(['crm', 'configure',
                                              'get-property',
                                              'maintenance-mode'],
                                             universal_newlines=True)

    @mock.patch('subprocess.check_output')
    @mock.patch.object(pcmk, 'crm_version')
    def test_get_property_from_xml(self, mock_crm_version, mock_check_output):
        mock_crm_version.return_value = StrictVersion('1.2.5')  # trusty
        mock_check_output.return_value = CRM_CONFIGURE_SHOW_XML
        self.assertRaises(pcmk.PropertyNotFound, pcmk.get_property,
                          'maintenance-mode')

        mock_check_output.assert_called_with(['crm', 'configure',
                                              'show', 'xml'],
                                             universal_newlines=True)
        mock_check_output.reset_mock()
        mock_check_output.return_value = CRM_CONFIGURE_SHOW_XML_MAINT_MODE_TRUE
        self.assertEqual('true', pcmk.get_property('maintenance-mode'))

        mock_check_output.assert_called_with(['crm', 'configure',
                                              'show', 'xml'],
                                             universal_newlines=True)

    @mock.patch('subprocess.check_output')
    def test_set_property(self, mock_check_output):
        pcmk.set_property('maintenance-mode', 'false')
        mock_check_output.assert_called_with(['crm', 'configure', 'property',
                                              'maintenance-mode=false'],
                                             universal_newlines=True)

    @mock.patch('subprocess.call')
    def test_crm_update_resource(self, mock_call):
        mock_call.return_value = 0

        with mock.patch.object(tempfile, "NamedTemporaryFile",
                               side_effect=lambda: self.tmpfile):
            pcmk.crm_update_resource('res_test', 'IPaddr2',
                                     ('params ip=1.2.3.4 '
                                      'cidr_netmask=255.255.0.0'))

        mock_call.assert_any_call(['crm', 'configure', 'load',
                                   'update', self.tmpfile.name])
        with open(self.tmpfile.name, 'r') as f:
            self.assertEqual(f.read(),
                             ('primitive res_test IPaddr2 \\\n'
                              '\tparams ip=1.2.3.4 cidr_netmask=255.255.0.0'))

    @mock.patch('commands.getstatusoutput')
    def test_crm_opt_exists(self, mock_getstatusoutput):
        mock_getstatusoutput.return_value = (0,
                                             CRM_CONFIGURE_SHOW_XML_OPT_EXISTS)
        self.assertTrue(pcmk.crm_opt_exists(
            'res_ceph-radosgw_public_hostname'))
        self.assertFalse(pcmk.crm_opt_exists('foobar'))
        self.assertFalse(pcmk.crm_opt_exists('rsc-options'))

        mock_getstatusoutput.return_value = (1, 'error')
        self.assertRaises(pcmk.PcmkError, pcmk.crm_opt_exists,
                          'res_ceph-radosgw_public_hostname')
