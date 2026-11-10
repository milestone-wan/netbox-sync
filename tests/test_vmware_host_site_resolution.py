# -*- coding: utf-8 -*-
#  Copyright (c) 2020 - 2026 netbox-sync team. All rights reserved.
#
#  netbox-sync.py
#
#  This work is licensed under the terms of the MIT license.
#  For a copy, see file LICENSE.txt included in this
#  repository or visit: <https://opensource.org/licenses/MIT>.

"""
Host site resolution: host_site_relation wins, else longest site-scoped prefix of the
primary IP, else the source default site. Cluster site no longer overrides the host.
"""
import re
from types import SimpleNamespace

from module.netbox.object_classes import NBCluster, NBDevice, NBPrefix, NBSite
from module.sources.vmware.connection import VMWareHandler


def _relation(pattern, assigned_name):
    return [{"object_regex": re.compile(pattern), "assigned_name": assigned_name}]


def _make_source(inventory, name="vc1", host_site_relation=None, cluster_site_relation=None):
    src = VMWareHandler.__new__(VMWareHandler)
    src.inventory = inventory
    src.name = name
    src.source_tag = f"Source: {name}"
    src.site_name = f"vCenter: {name}"
    src.host_site_resolutions = {}
    src.cluster_scope_from_config = {}
    src.settings = SimpleNamespace(
        host_site_relation=host_site_relation or [],
        cluster_site_relation=cluster_site_relation or [],
    )
    inventory.add_source(src)
    return src


def test_get_site_name_for_host_ignores_cluster_site(inventory):
    src = _make_source(
        inventory,
        host_site_relation=_relation("esxi1", "HostSite"),
        cluster_site_relation=_relation(".*", "ClusterSite"),
    )

    assert src.get_site_name(NBDevice, "esxi1", "DC/Cluster1") == "HostSite"
    assert src.get_site_name(NBDevice, "esxi-other", "DC/Cluster1") is None
    assert src.get_site_name(NBCluster, "DC/Cluster1") == "ClusterSite"


def test_resolve_host_site_uses_config_as_strong(inventory):
    src = _make_source(inventory, host_site_relation=_relation("esxi1", "ConfigSite"))
    inventory.add_object(NBSite, data={"id": 1, "name": "PrefixSite"}, read_from_netbox=True)
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.0.0/24", "scope_type": "dcim.site", "scope_id": 1},
        read_from_netbox=True,
    )
    inventory.resolve_relations()

    site_name, strong = src.resolve_host_site("esxi1", primary_ip4="10.0.0.5/24")

    assert site_name == "ConfigSite"
    assert strong is True


def test_resolve_host_site_uses_longest_site_prefix(inventory):
    src = _make_source(inventory)
    site = inventory.add_object(NBSite, data={"id": 1, "name": "PrefixSite"}, read_from_netbox=True)
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.0.0/16", "scope_type": "dcim.site", "scope_id": site.nb_id},
        read_from_netbox=True,
    )
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.1.0/24", "scope_type": "dcim.site", "scope_id": site.nb_id},
        read_from_netbox=True,
    )
    inventory.add_object(NBPrefix, data={"prefix": "10.0.1.0/24"}, read_from_netbox=True)
    inventory.resolve_relations()

    site_name, strong = src.resolve_host_site("esxi1", primary_ip4="10.0.1.10/24")

    assert site_name == "PrefixSite"
    assert strong is True


def test_resolve_host_site_falls_back_to_default_on_prefix_tie(inventory):
    src = _make_source(inventory)
    site_a = inventory.add_object(NBSite, data={"id": 1, "name": "site-a"}, read_from_netbox=True)
    site_b = inventory.add_object(NBSite, data={"id": 2, "name": "site-b"}, read_from_netbox=True)
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.0.0/24", "scope_type": "dcim.site", "scope_id": site_a.nb_id},
        read_from_netbox=True,
    )
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.0.0/24", "scope_type": "dcim.site", "scope_id": site_b.nb_id},
        read_from_netbox=True,
    )
    inventory.resolve_relations()

    site_name, strong = src.resolve_host_site("esxi1", primary_ip4="10.0.0.5/24")

    assert site_name == "vCenter: vc1"
    assert strong is False


def test_resolve_host_site_prefers_ipv4_over_ipv6(inventory):
    src = _make_source(inventory)
    site_v4 = inventory.add_object(NBSite, data={"id": 1, "name": "v4-site"}, read_from_netbox=True)
    site_v6 = inventory.add_object(NBSite, data={"id": 2, "name": "v6-site"}, read_from_netbox=True)
    inventory.add_object(
        NBPrefix,
        data={"prefix": "10.0.0.0/24", "scope_type": "dcim.site", "scope_id": site_v4.nb_id},
        read_from_netbox=True,
    )
    inventory.add_object(
        NBPrefix,
        data={"prefix": "fd00::/64", "scope_type": "dcim.site", "scope_id": site_v6.nb_id},
        read_from_netbox=True,
    )
    inventory.resolve_relations()

    site_name, strong = src.resolve_host_site(
        "esxi1", primary_ip4="10.0.0.5/24", primary_ip6="fd00::1/64"
    )

    assert site_name == "v4-site"
    assert strong is True
