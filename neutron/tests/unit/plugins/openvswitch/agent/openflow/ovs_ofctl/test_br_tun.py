# Copyright (C) 2014,2015 VA Linux Systems Japan K.K.
# Copyright (C) 2014,2015 YAMAMOTO Takashi <yamamoto at valinux co jp>
# All Rights Reserved.
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

import mock
import netaddr

import neutron.plugins.openvswitch.common.constants as ovs_const
from neutron.tests.unit.plugins.openvswitch.agent.openflow.ovs_ofctl \
    import ovs_bridge_test_base


call = mock.call  # short hand


class OVSTunnelBridgeTest(ovs_bridge_test_base.OVSBridgeTestBase,
                          ovs_bridge_test_base.OVSDVRProcessTestMixin):
    dvr_process_table_id = ovs_const.DVR_PROCESS
    dvr_process_next_table_id = ovs_const.PATCH_LV_TO_TUN

    def setUp(self):
        super(OVSTunnelBridgeTest, self).setUp()
        self.setup_bridge_mock('br-tun', self.br_tun_cls)

    def test_setup_default_table(self):
        patch_int_ofport = 5555
        arp_responder_enabled = False
        self.br.setup_default_table(patch_int_ofport=patch_int_ofport,
            arp_responder_enabled=arp_responder_enabled)
        expected = [
            call.add_flow(priority=1, in_port=patch_int_ofport,
                          actions='resubmit(,2)'),
            call.add_flow(priority=0, actions='drop'),
            call.add_flow(priority=0, table=2,
                          dl_dst='00:00:00:00:00:00/01:00:00:00:00:00',
                          actions='resubmit(,20)'),
            call.add_flow(priority=0, table=2,
                          dl_dst='01:00:00:00:00:00/01:00:00:00:00:00',
                          actions='resubmit(,22)'),
            call.add_flow(priority=0, table=3, actions='drop'),
            call.add_flow(priority=0, table=4, actions='drop'),
            call.add_flow(priority=1, table=10,
                          actions='learn(table=20,priority=1,'
                          'hard_timeout=300,NXM_OF_VLAN_TCI[0..11],'
                          'NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],'
                          'load:0->NXM_OF_VLAN_TCI[],'
                          'load:NXM_NX_TUN_ID[]->NXM_NX_TUN_ID[],'
                          'output:NXM_OF_IN_PORT[]),'
                          'output:%s' % patch_int_ofport),
            call.add_flow(priority=0, table=20, actions='resubmit(,22)'),
            call.add_flow(priority=0, table=22, actions='drop'),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_setup_default_table_arp_responder_enabled(self):
        patch_int_ofport = 5555
        arp_responder_enabled = True
        self.br.setup_default_table(patch_int_ofport=patch_int_ofport,
            arp_responder_enabled=arp_responder_enabled)
        expected = [
            call.add_flow(priority=1, in_port=patch_int_ofport,
                          actions='resubmit(,2)'),
            call.add_flow(priority=0, actions='drop'),
            call.add_flow(priority=1, table=2, dl_dst='ff:ff:ff:ff:ff:ff',
                          actions='resubmit(,21)', proto='arp'),
            call.add_flow(priority=0, table=2,
                          dl_dst='00:00:00:00:00:00/01:00:00:00:00:00',
                          actions='resubmit(,20)'),
            call.add_flow(priority=0, table=2,
                          dl_dst='01:00:00:00:00:00/01:00:00:00:00:00',
                          actions='resubmit(,22)'),
            call.add_flow(priority=0, table=3, actions='drop'),
            call.add_flow(priority=0, table=4, actions='drop'),
            call.add_flow(priority=1, table=10,
                          actions='learn(table=20,priority=1,'
                          'hard_timeout=300,NXM_OF_VLAN_TCI[0..11],'
                          'NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],'
                          'load:0->NXM_OF_VLAN_TCI[],'
                          'load:NXM_NX_TUN_ID[]->NXM_NX_TUN_ID[],'
                          'output:NXM_OF_IN_PORT[]),'
                          'output:%s' % patch_int_ofport),
            call.add_flow(priority=0, table=20, actions='resubmit(,22)'),
            call.add_flow(priority=0, table=21, actions='resubmit(,22)'),
            call.add_flow(priority=0, table=22, actions='drop'),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_provision_local_vlan(self):
        network_type = 'vxlan'
        lvid = 888
        segmentation_id = 777
        distributed = False
        self.br.provision_local_vlan(network_type=network_type, lvid=lvid,
                                     segmentation_id=segmentation_id,
                                     distributed=distributed)
        expected = [
            call.add_flow(priority=1, tun_id=segmentation_id,
                          actions='mod_vlan_vid:%s,resubmit(,10)' % lvid,
                          table=4),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_reclaim_local_vlan(self):
        network_type = 'vxlan'
        segmentation_id = 777
        self.br.reclaim_local_vlan(network_type=network_type,
                                   segmentation_id=segmentation_id)
        expected = [
            call.delete_flows(tun_id=segmentation_id, table=4),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_install_flood_to_tun(self):
        vlan = 3333
        tun_id = 2222
        ports = [11, 44, 22, 33]
        self.br.install_flood_to_tun(vlan=vlan,
                                     tun_id=tun_id,
                                     ports=ports)
        expected = [
            call.mod_flow(table=22, dl_vlan=vlan,
                          actions='strip_vlan,set_tunnel:%(tun)s,'
                          'output:%(ports)s' % {
                              'tun': tun_id,
                              'ports': ','.join(map(str, ports)),
                          }),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_delete_flood_to_tun(self):
        vlan = 3333
        self.br.delete_flood_to_tun(vlan=vlan)
        expected = [
            call.delete_flows(table=22, dl_vlan=vlan),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_install_unicast_to_tun(self):
        vlan = 3333
        port = 55
        mac = '08:60:6e:7f:74:e7'
        tun_id = 2222
        self.br.install_unicast_to_tun(vlan=vlan,
                                       tun_id=tun_id,
                                       port=port,
                                       mac=mac)
        expected = [
            call.add_flow(priority=2, table=20, dl_dst=mac, dl_vlan=vlan,
                          actions='strip_vlan,set_tunnel:%(tun)s,'
                          'output:%(port)s' % {
                              'tun': tun_id,
                              'port': port,
                          }),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_delete_unicast_to_tun(self):
        vlan = 3333
        mac = '08:60:6e:7f:74:e7'
        self.br.delete_unicast_to_tun(vlan=vlan, mac=mac)
        expected = [
            call.delete_flows(table=20, dl_dst=mac, dl_vlan=vlan),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_delete_unicast_to_tun_without_mac(self):
        vlan = 3333
        mac = None
        self.br.delete_unicast_to_tun(vlan=vlan, mac=mac)
        expected = [
            call.delete_flows(table=20, dl_vlan=vlan),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_install_arp_responder(self):
        vlan = 3333
        ip = '192.0.2.1'
        mac = '08:60:6e:7f:74:e7'
        self.br.install_arp_responder(vlan=vlan, ip=ip, mac=mac)
        expected = [
            call.add_flow(proto='arp', nw_dst=ip,
                          actions='move:NXM_OF_ETH_SRC[]->NXM_OF_ETH_DST[],'
                          'mod_dl_src:%(mac)s,load:0x2->NXM_OF_ARP_OP[],'
                          'move:NXM_NX_ARP_SHA[]->NXM_NX_ARP_THA[],'
                          'move:NXM_OF_ARP_SPA[]->NXM_OF_ARP_TPA[],'
                          'load:%(mac)#x->NXM_NX_ARP_SHA[],'
                          'load:%(ip)#x->NXM_OF_ARP_SPA[],in_port' % {
                              'mac': netaddr.EUI(mac,
                                                 dialect=netaddr.mac_unix),
                              'ip': netaddr.IPAddress(ip),
                          },
                          priority=1, table=21, dl_vlan=vlan),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_delete_arp_responder(self):
        vlan = 3333
        ip = '192.0.2.1'
        self.br.delete_arp_responder(vlan=vlan, ip=ip)
        expected = [
            call.delete_flows(table=21, dl_vlan=vlan, proto='arp', nw_dst=ip),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_delete_arp_responder_without_ip(self):
        vlan = 3333
        ip = None
        self.br.delete_arp_responder(vlan=vlan, ip=ip)
        expected = [
            call.delete_flows(table=21, dl_vlan=vlan, proto='arp'),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_setup_tunnel_port(self):
        network_type = 'vxlan'
        port = 11111
        self.br.setup_tunnel_port(network_type=network_type, port=port)
        expected = [
            call.add_flow(priority=1, in_port=port, actions='resubmit(,4)'),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_cleanup_tunnel_port(self):
        port = 11111
        self.br.cleanup_tunnel_port(port=port)
        expected = [
            call.delete_flows(in_port=port),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_add_dvr_mac_tun(self):
        mac = '00:02:b3:13:fe:3d'
        port = 8888
        self.br.add_dvr_mac_tun(mac=mac, port=port)
        expected = [
            call.add_flow(priority=1, table=9, dl_src=mac,
                          actions='output:%s' % port),
        ]
        self.assertEqual(expected, self.mock.mock_calls)

    def test_remove_dvr_mac_tun(self):
        mac = '00:02:b3:13:fe:3d'
        self.br.remove_dvr_mac_tun(mac=mac)
        expected = [
            call.delete_flows(eth_src=mac, table_id=9),
        ]
        self.assertEqual(expected, self.mock.mock_calls)
