import ipaddress
import random
import requests
import socket

from lib.log import log


# Endpoint to determine our public facing IP for device-server
public_ip_url = "http://ip.42.pl/raw"
# Bunq server address range
bunq_network = "185.40.108.0/22"


def is_bunq_server(ip):
    return ipaddress.ip_address(ip) in ipaddress.ip_network(bunq_network)


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def is_private_ip(ip):
    return ipaddress.ip_address(ip).is_private


def get_public_ip():
    local_ip = get_local_ip()
    if not is_private_ip(local_ip):
        return local_ip
    external_ip = get_portmap_external_ip()
    if external_ip:
        return external_ip
    log.info("Retrieving public IP from {}...".format(public_ip_url))
    return requests.get(public_ip_url).text


def get_hostname():
    fqdn = socket.getfqdn()
    if "localhost" not in fqdn:
        return fqdn
    return socket.gethostname()


upnp_init = False
upnp = None


def portmap_setup():
    global upnp_init, upnp
    if upnp_init:
        return
    upnp_init = True
    try:
        import miniupnpc
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 3
    except ImportError:
        log.warning("Could not load miniupnpc module. Skipping upnp " +
                        "port mapping.")


def portmap_search():
    if not upnp:
        return
    log.info("Searching for upnp gateway...")
    try:
        upnp.discover()
        upnp.selectigd()
    except Exception as e:
        log.error("Error searching for upnp gateway: {0}".format(e))


def get_portmap_external_ip():
    if not upnp:
        return None
    try:
        external_ip = upnp.externalipaddress()
        log.info("Retrieved external IP {} from upnp gateway..."
                 .format(external_ip))
        return external_ip
    except:
        return None


def portmap_add(external_port, local_port, marker):
    if not upnp:
        return
    log.info("Adding upnp port mapping...")
    try:
        upnp.addportmapping(external_port, 'TCP', upnp.lanaddr, local_port,
                            marker, '')
        return eternal_port
    except Exception as e:
        log.error("Failed to map port: {}".format(e))


# Multiply tries to find a suitable port
def portmap_seek(local_port, marker):
    if not upnp:
        return
    try_port = local_port
    log.info("Adding upnp port mapping...")
    for i in range(0, 128):
        try:
            upnp.addportmapping(try_port, 'TCP', upnp.lanaddr, local_port,
                                marker, '')
            return try_port
        except Exception as e:
            if "ConflictInMappingEntry" not in str(e):
                log.error("Failed to map port: {}".format(e))
                return
            log.info("Port {} is already mapped, trying next port..."
                  .format(try_port))
            try_port = random.randint(1025, 65535)


def portmap_remove(port):
    if not upnp or not port:
        return
    log.info("Removing upnp port {} mapping...".format(port))
    try:
        result = upnp.deleteportmapping(port, 'TCP')
        if not result:
            log.error("Failed to remove upnp port mapping.")
    except Exception as e:
        log.error("Error removing upnp port mapping: {0}".format(e))
