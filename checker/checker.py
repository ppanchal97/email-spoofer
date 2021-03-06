#! /usr/bin/env python3

import sys

import emailprotectionslib.dmarc as dmarclib
import emailprotectionslib.spf as spflib
import logging

from libs.PrettyOutput import output_good, output_bad, \
    output_info, output_error, output_indifferent

from colorama import init as color_init

logging.basicConfig(level=logging.INFO)


def check_spf_redirect_mechanisms(spf_record):
    redirect_domain = spf_record.get_redirect_domain()

    if redirect_domain:
        output_info(f"Processing an SPF redirect domain: {redirect_domain}")
        return is_spf_record_strong(redirect_domain)
    else:
        return False


def check_spf_include_mechanisms(spf_record):
    include_domain_list = spf_record.get_include_domains()

    for include_domain in include_domain_list:
        output_info(f"Processing an SPF include domain: {include_domain}")
        strong_all_string = is_spf_record_strong(include_domain)

        if strong_all_string:
            return True

    return False


def is_spf_redirect_record_strong(spf_record):
    output_info(
        f"Checking SPF redirect domain: {spf_record.get_redirect_domain}")
    redirect_strong = spf_record._is_redirect_mechanism_strong()

    if redirect_strong:
        output_bad("Redirect mechanism is strong.")
    else:
        output_indifferent("Redirect mechanism is not strong.")

    return redirect_strong


def are_spf_include_mechanisms_strong(spf_record):
    output_info("Checking SPF include mechanisms")
    include_strong = spf_record._are_include_mechanisms_strong()

    if include_strong:
        output_bad("Include mechanisms include a strong record")
    else:
        output_indifferent("Include mechanisms are not strong")

    return include_strong


def check_spf_include_redirect(spf_record):
    other_records_strong = False

    if spf_record.get_redirect_domain():
        other_records_strong = is_spf_redirect_record_strong(spf_record)

    if not other_records_strong:
        other_records_strong = are_spf_include_mechanisms_strong(spf_record)

    return other_records_strong


def check_spf_all_string(spf_record):
    strong_spf_all_string = True

    if spf_record.all_string:
        # Strong SPF protection if -all is included
        if spf_record.all_string == "~all" or spf_record.all_string == "-all":
            output_indifferent(
                f"SPF record contains an All item: {spf_record.all_string}")
        else:
            output_good(
                f"SPF record All item is too weak: {spf_record.all_string}")
            strong_spf_all_string = False

    else:
        output_good("SPF record has no All string")
        strong_spf_all_string = False

    if not strong_spf_all_string:
        strong_spf_all_string = check_spf_include_redirect(spf_record)

    return strong_spf_all_string


def is_spf_record_strong(domain):
    strong_spf_record = True

    spf_record = spflib.SpfRecord.from_domain(domain)
    if spf_record and spf_record.record:
        output_info("Found SPF record:")
        output_info(str(spf_record.record))

        strong_all_string = check_spf_all_string(spf_record)
        if not strong_all_string:

            redirect_strength = check_spf_redirect_mechanisms(spf_record)
            include_strength = check_spf_include_mechanisms(spf_record)
            strong_spf_record = False

            if redirect_strength or include_strength:
                strong_spf_record = True
    else:
        output_good(f"{domain} has no SPF record!")
        strong_spf_record = False
    return strong_spf_record


def get_dmarc_record(domain):
    dmarc = dmarclib.DmarcRecord.from_domain(domain)
    if dmarc and dmarc.record:
        output_info("Found DMARC record:")
        output_info(str(dmarc.record))
    return dmarc


def get_dmarc_org_record(base_record):
    org_record = base_record.get_org_record()
    if org_record:
        output_info("Found DMARC Organizational record:")
        output_info(str(org_record.record))
    return org_record


def check_dmarc_extras(dmarc_record):
    if dmarc_record.pct and dmarc_record.pct != str(100):
        output_indifferent(
            f"DMARC pct is set to {dmarc_record.pct}% - might be possible")

    if dmarc_record.rua:
        output_indifferent(
            f"Aggregate reports will be sent: {dmarc_record.rua}")

    if dmarc_record.ruf:
        output_indifferent(
            f"Forensics reports will be sent: {dmarc_record.ruf}")


def check_dmarc_policy(dmarc_record):
    policyStrong = False

    if dmarc_record.policy:
        if dmarc_record.policy == "reject" or dmarc_record.policy == "quarantine":
            policyStrong = True
            output_bad(f"DMARC policy set to {dmarc_record.policy}")
        else:
            output_good(f"DMARC policy set to {dmarc_record.policy}")
    else:
        output_good("DMARC record has no Policy")

    return policyStrong


def check_dmarc_org_policy(base_record):
    policy_strong = False

    try:
        org_record = base_record.get_org_record()
        if org_record and org_record.record:
            output_info("Found organizational DMARC record:")
            output_info(str(org_record.record))

            if org_record.subdomain_policy:
                if org_record.subdomain_policy == "none":
                    output_good(
                        f"Organizational subdomain policy set to {org_record.subdomain_policy}")
                elif org_record.subdomain_policy == "quarantine" or org_record.subdomain_policy == "reject":
                    output_bad(
                        f"Organizational subdomain policy explicitly set to {org_record.subdomain_policy}")
                    policy_strong = True
            else:
                output_info(
                    "No explicit organizational subdomain policy. Defaulting to organizational policy...")
                policy_strong = check_dmarc_policy(org_record)
        else:
            output_good("No organizational DMARC record")

    except dmarclib.OrgDomainException:
        output_good("No organizational DMARC record")

    except Exception as e:
        logging.exception(e)

    return policy_strong


def is_dmarc_record_strong(domain):
    dmarc_record_strong = False

    dmarc = get_dmarc_record(domain)

    if dmarc and dmarc.record:
        dmarc_record_strong = check_dmarc_policy(dmarc)

        check_dmarc_extras(dmarc)

    elif dmarc.get_org_domain():
        output_info(
            "No DMARC record found. Looking for organizational record...")
        dmarc_record_strong = check_dmarc_org_policy(dmarc)

    else:
        output_good(f"{domain} has no DMARC record!")

    return dmarc_record_strong


if __name__ == "__main__":
    color_init()
    
    try:
        domain = sys.argv[1]
        """
        A DMARC Record can have p=none, p=quarantine, or p=reject. When the policy is set to quarantine, emails that fail SPF or DKIM checks 
        are usually delivered to the spam folder. When the policy is set to reject, emails that fail the checks are not delivered at all.
        Nearly all Mail Transport Agents, including the ones used by Gmail and Microsoft Exchange Server, default to relying on DMARC for 
        direction on what action to take if an email fails SPF or DKIM. If the sending domain has no DMARC record or a record with a 
        policy of none, the mail server fails open and delivers the email. This means that if a domain does not have an SPF, DKIM, AND a 
        *strict DMARC record*, it can be spoofed.
        """
        if is_spf_record_strong(domain) and is_dmarc_record_strong(domain):
            output_bad(f"Spoofing not possible for {domain}")
        else:
            output_good(f"Spoofing possible for {domain}!")

    except IndexError:
        output_error(f"Usage: {sys.argv[0]} [DOMAIN]")
