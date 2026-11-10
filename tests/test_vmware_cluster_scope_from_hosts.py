# -*- coding: utf-8 -*-
#  Copyright (c) 2020 - 2026 netbox-sync team. All rights reserved.
#
#  netbox-sync.py
#
#  This work is licensed under the terms of the MIT license.
#  For a copy, see file LICENSE.txt included in this
#  repository or visit: <https://opensource.org/licenses/MIT>.

"""
After hosts are parsed, clusters without a config site get scoped from unanimous
strong host sites, or left empty when hosts disagree.
"""
from types import SimpleNamespace

from module.netbox.object_classes import NBCluster, NBClusterType, NBSite
from module.sources.vmware.connection import VMWareHandler


def _make_source(inventory, name="vc1"):
    src = VMWareHandler.__new__(VMWareHandler)
    src.inventory = inventory
    src.name = name
    src.source_tag = f"Source: {name}"
    src.site_name = f"vCenter: {name}"
    src.host_site_resolutions = {}
    src.cluster_scope_from_config = {}
    src.settings = SimpleNamespace()
    inventory.netbox_api_version = "4.3.0"
    inventory.add_source(src)
    return src


def _cluster(inventory, name="c1"):
    ctype = inventory.add_object(NBClusterType, data={"name": "VMware ESXi"}, read_from_netbox=True)
    return inventory.add_object(NBCluster, data={"name": name, "type": ctype}, read_from_netbox=True)


def test_unanimous_strong_host_sites_set_cluster_scope(inventory):
    src = _make_source(inventory)
    cluster = _cluster(inventory)
    site = inventory.add_object(NBSite, data={"name": "NYC"}, read_from_netbox=True)
    src.host_site_resolutions = {
        "esxi1": {"site_name": "NYC", "strong": True, "cluster": cluster},
        "esxi2": {"site_name": "NYC", "strong": True, "cluster": cluster},
        "esxi3": {"site_name": "vCenter: vc1", "strong": False, "cluster": cluster},
    }

    src.resolve_cluster_scopes_from_hosts()

    assert cluster.data.get("scope_type") == "dcim.site"
    assert cluster.data.get("scope_id") is site or cluster.data.get("scope_id").get_display_name() == "NYC"


def test_disagreeing_strong_host_sites_leave_cluster_unscoped(inventory):
    src = _make_source(inventory)
    cluster = _cluster(inventory)
    inventory.add_object(NBSite, data={"name": "NYC"}, read_from_netbox=True)
    inventory.add_object(NBSite, data={"name": "FFM"}, read_from_netbox=True)
    src.host_site_resolutions = {
        "esxi1": {"site_name": "NYC", "strong": True, "cluster": cluster},
        "esxi2": {"site_name": "FFM", "strong": True, "cluster": cluster},
    }

    src.resolve_cluster_scopes_from_hosts()

    assert cluster.data.get("scope_type") is None
    assert cluster.data.get("scope_id") is None


def test_config_scoped_cluster_is_not_overwritten(inventory):
    src = _make_source(inventory)
    site = inventory.add_object(NBSite, data={"name": "ConfigSite"}, read_from_netbox=True)
    ctype = inventory.add_object(NBClusterType, data={"name": "VMware ESXi"}, read_from_netbox=True)
    cluster = inventory.add_object(
        NBCluster,
        data={"name": "c1", "type": ctype, "scope_type": "dcim.site", "scope_id": site},
        read_from_netbox=True,
    )
    src.cluster_scope_from_config[id(cluster)] = True
    inventory.add_object(NBSite, data={"name": "PrefixSite"}, read_from_netbox=True)
    src.host_site_resolutions = {
        "esxi1": {"site_name": "PrefixSite", "strong": True, "cluster": cluster},
    }

    src.resolve_cluster_scopes_from_hosts()

    assert cluster.data.get("scope_id") is site
