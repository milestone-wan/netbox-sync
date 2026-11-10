# -*- coding: utf-8 -*-
#  Copyright (c) 2020 - 2026 netbox-sync team. All rights reserved.
#
#  netbox-sync.py
#
#  This work is licensed under the terms of the MIT license.
#  For a copy, see file LICENSE.txt included in this
#  repository or visit: <https://opensource.org/licenses/MIT>.

"""
VMs inherit the parent host's resolved site (config or prefix), not the cluster site.
"""
from types import SimpleNamespace

from module.netbox.object_classes import NBCluster, NBClusterType, NBSite
from module.sources.vmware.connection import VMWareHandler


def _make_source(inventory):
    src = VMWareHandler.__new__(VMWareHandler)
    src.inventory = inventory
    src.name = "vc1"
    src.source_tag = "Source: vc1"
    src.site_name = "vCenter: vc1"
    src.host_site_resolutions = {}
    src.cluster_scope_from_config = {}
    src.settings = SimpleNamespace(strip_host_domain_name=True, cluster_site_relation=[])
    inventory.add_source(src)
    return src


def test_vm_site_follows_parent_host_not_cluster(inventory):
    src = _make_source(inventory)
    cluster_site = inventory.add_object(NBSite, data={"name": "ClusterSite"}, read_from_netbox=True)
    ctype = inventory.add_object(NBClusterType, data={"name": "VMware ESXi"}, read_from_netbox=True)
    cluster = inventory.add_object(
        NBCluster,
        data={"name": "c1", "type": ctype, "scope_type": "dcim.site", "scope_id": cluster_site},
        read_from_netbox=True,
    )
    cluster.resolve_relations()
    src.host_site_resolutions["esxi1"] = {
        "site_name": "HostSite",
        "strong": True,
        "cluster": cluster,
    }

    site_name, strong = src.resolve_vm_site("esxi1", cluster, "DC/c1")

    assert site_name == "HostSite"
    assert strong is True


def test_vm_falls_back_to_cluster_site_without_host_resolution(inventory):
    src = _make_source(inventory)
    cluster_site = inventory.add_object(NBSite, data={"name": "ClusterSite"}, read_from_netbox=True)
    ctype = inventory.add_object(NBClusterType, data={"name": "VMware ESXi"}, read_from_netbox=True)
    cluster = inventory.add_object(
        NBCluster,
        data={"name": "c1", "type": ctype, "scope_type": "dcim.site", "scope_id": cluster_site},
        read_from_netbox=True,
    )
    cluster.resolve_relations()

    site_name, strong = src.resolve_vm_site("esxi-missing", cluster, "DC/c1")

    assert site_name == "ClusterSite"
    assert strong is False
