REVISION_NEEDED
1. **Factual error in the threat section (Common Attack Techniques → Injection attacks).** The XSS mitigation is correct, but the framing is loose: XSS is described as an attacker placing a script "that other users then load and run," which is accurate for stored XSS only. Reflected and DOM-based XSS are omitted, and the chapter should say it covers stored XSS specifically or broaden the sentence.

2. **Factual error in Passkeys.** "A passkey bound to a domain cannot be replayed on a look-alike site" is accurate, but "removes the phishing risk that passwords cannot eliminate" overstates it. Passkeys remove credential-phishing against the passkey itself, not all phishing (e.g., session hijacking via adversary-in-the-middle proxies is reduced, not eliminated, and account recovery paths can still be phished). Qualify the claim.

3. **Factual error in Cryptography → Hashing.** "Hashing protects data *at rest* when used for password storage" conflates two ideas. Hashing protects stored passwords by making recovery harder; it does not protect data at rest in general (that is encryption). Reword to separate password hashing from at-rest encryption.

4. **Imprecise statement in Cryptography → Digital signatures.** "The signer hashes a document and encrypts the hash with a private key" is a common simplification. Modern schemes (e.g., ECDSA, Ed25519, RSA-PSS) sign the hash using a signing operation, not encryption in the strict sense. Either say "signs the hash with the private key" or note the simplification.

5. **Accuracy in Identity and Access Management.** "Something you *are*" is correct, but the SMS point should note that SMS and the phone can also be compromised by SIM swapping, which is the actual reason SMS is weaker. The current wording ("a phone that the attacker has also compromised") is vague.

6. **Missing mitigation for DoS in Network section.** The chapter describes DoS mitigation but never mentions that rate limiting alone does not stop volumetric (network-layer) floods; upstream filtering is needed. This is partly implied but should be explicit so readers do not rely on rate limiting for volumetric attacks.

7. **Clarity: "Logs are useful only if..." paragraph.** The metaphor "evidence written for an investigator who never arrives" is clever but obscures the point. State plainly: logs must be centralized, tamper-protected, retained, and reviewed.

8. **Completeness: missing topic on supply-chain or third-party risk.** Given the chapter's stated scope ("how attackers actually work"), it omits supply-chain compromise (malicious dependencies, compromised build pipelines), which is among the most significant recent attack classes. A short paragraph or a bullet in Malware or Application security would close this gap.

9. **Clarity: Incident response phase 1.** "Preparation" lists "ensuring logging and backups are in place," which belongs in preparation but the list is otherwise clean; no change needed there. However, the framing "reflected in NIST guidance" should cite the document (NIST SP 800-61) so readers can verify it.

10. **Minor style.** "behaviour" (British) is used while the rest of the chapter uses American spelling elsewhere ("behavior" is not used, so check consistency across the document).