"""Compact candidate-local diagnostics, grounded in FRR's actual rejection."""
from ipaddress import IPv4Interface
import re


def observation(result, config_text, router):
    raw = {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    text = result.stdout + result.stderr
    rejected = []
    for match in re.finditer(r'line (\d+): % Unknown command\[\d+\]:\s*([^\n]+)', text):
        rejected.append({'line': int(match[1]), 'statement': match[2].strip()})
    for match in re.finditer(r'line (\d+): Failure to communicate\[\d+\].*?line:\s*([^\n]+)', text):
        rejected.append({'line': int(match[1]), 'statement': match[2].strip()})
    diagnostic = {}
    if any(item['statement']=='exit-address-family' for item in rejected):
        lines=config_text.splitlines()
        for closing in [item['line'] for item in rejected if item['statement']=='exit-address-family']:
            starts=[i for i,line in enumerate(lines[:closing-1],1) if line.strip()=='address-family ipv4 unicast']
            if not starts:
                continue
            start=starts[-1]
            misplaced=[{'line':i,'statement':line.strip()} for i,line in enumerate(lines,1)
                       if start<i<closing and re.fullmatch(r'neighbor\s+\S+\s+remote-as\s+\S+',line.strip())]
            if misplaced:
                diagnostic['bgp_context_hint']={
                    'diagnostic_version':'frr-bgp-context-hint-v1',
                    'address_family_line':start,'rejected_closing_line':closing,
                    'remote_as_after_address_family':misplaced,
                    'explanation':'Neighbor remote-as declarations belong to router bgp context and may leave the address-family context. Declare them before entering address-family; keep activate and route-map attachments inside the address-family.',
                    'kind':'candidate-local context hint; FRR rejection is the observed failure'}
                break
    if rejected:
        diagnostic['rejected_statements'] = rejected
    if 'Can not configure the local system as neighbor' in text:
        # This isolated load materializes the fixed public interface addresses.
        addresses = {str(IPv4Interface(i.ipv4).ip): i.name for i in router.interfaces}
        conflicts = []
        for line in config_text.splitlines():
            words = line.split()
            if len(words) >= 4 and words[0] == 'neighbor' and words[2] == 'remote-as' and words[1] in addresses:
                conflicts.append({'statement': line.strip(), 'local_interface': addresses[words[1]],
                                  'local_address': words[1]})
        if conflicts:
            diagnostic['neighbor_address_is_local'] = conflicts
    # Put salient details before the possibly long daemon transcript. Context
    # bounding retains this prefix; original command evidence remains byte-exact.
    return {'diagnostics': diagnostic, **raw} if diagnostic else raw


def unresolved_bgp_route_maps(text):
    """Direct neighbor policy references missing a definition in a full config.

    Syntax gate applies this to FRR's final running-config, so definitions after
    attachments are supported and transient load warnings alone do not fail.
    """
    definitions = set(re.findall(r'^\s*route-map\s+(\S+)\s+(?:permit|deny)\s+\d+\s*$', text, re.M))
    missing = []
    for match in re.finditer(r'^\s*neighbor\s+(\S+)\s+route-map\s+(\S+)\s+(in|out)\s*$', text, re.M):
        peer, name, direction = match.groups()
        if name not in definitions:
            missing.append({'peer':peer,'route_map':name,'direction':direction})
    return missing
