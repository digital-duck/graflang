## Chapter 2: Threats, Defenses, and Secure Practice

Every security control exists because someone, somewhere, is trying to get around it. This chapter looks at the other side of the ledger: how attackers actually work, and how defenders stack their countermeasures against those methods. Along the way, we will examine the tools that protect data and identities, the discipline needed to detect and respond to incidents, and the human habits that determine whether all the technology actually works.

### Common Attack Techniques

Most attacks are not sophisticated. They succeed because they exploit predictable weaknesses: a person who clicks a convincing link, a password reused across five websites, or a web form that trusts whatever it receives. Understanding the common techniques is the first step toward recognizing them and choosing the right defense.

**Phishing and social engineering** target people rather than machines. A phishing message impersonates a bank, a colleague, or a software vendor to trick the recipient into revealing credentials or opening a malicious file. Social engineering extends this to phone calls, impersonated IT staff, or staged in-person visits. *Mitigation:* email filtering, verification through a second channel before acting on unusual requests, and training that teaches staff to check sender addresses and hover over links.

**Malware** is software written to cause harm. Four types are especially common:
- **Ransomware** encrypts a victim's files and demands payment for the decryption key. *Mitigation:* offline, tested backups; least-privilege accounts so malware cannot reach shared drives; and patching the vulnerabilities ransomware typically uses to spread.
- **Trojans** disguise themselves as useful programs while secretly providing remote access or stealing data. *Mitigation:* application allowlisting and installing software only from trusted sources.
- **Worms** replicate across networks without user action. *Mitigation:* network segmentation to limit spread and prompt patching of exposed services.
- **Supply-chain compromises** insert malicious code upstream of the victim rather than attacking it directly. An attacker may publish a poisoned software package with a name close to a popular one (typosquatting), slip malicious code into a legitimate dependency whose maintainer account was taken over, or tamper with a build pipeline so that the compiled product carries a backdoor that the source code does not show. Such attacks are especially dangerous because the victim's own trusted update channel delivers the payload. *Mitigation:* pinning and reviewing dependencies, verifying package checksums and signatures, generating a software bill of materials (SBOM) so the components in use are known, restricting who can change build pipelines, and protecting build systems as carefully as production systems.

**Injection attacks** exploit the way applications mix untrusted input with commands. In **SQL injection**, an attacker types database syntax into a login field, and the application passes it straight to the database, which then runs the attacker's query. In **cross-site scripting (XSS)**, an attacker causes a script to be executed in another user's browser. This chapter addresses **stored XSS**, in which the malicious script is saved by the application (for example, in a comment field) and served to every visitor who loads that page. Two other forms are also common: **reflected XSS**, where the script is carried in a request (such as a crafted link) and echoed back in the response, and **DOM-based XSS**, where client-side JavaScript writes untrusted data into the page without the server ever seeing it. *Mitigation:* parameterized queries for databases, and output encoding plus content security policies for web pages, which address all three forms. The principle is the same in every case: never let data be interpreted as code.

**Credential attacks** attempt to obtain valid logins rather than break in. Attackers use *credential stuffing* (replaying username and password pairs leaked from other breaches), *password spraying* (trying one common password across many accounts to avoid lockouts), and *brute force* (systematically guessing). *Mitigation:* unique passwords, rate limiting, lockout or delay policies, and multi-factor authentication, which makes a stolen password insufficient on its own.

**Denial of service (DoS)** aims to make a service unavailable by overwhelming it with traffic or exhausting its resources. Volumetric attacks flood the network link itself with more traffic than it can carry, and no amount of work at the application can stop this, because the traffic never reaches it in a usable form. Application-layer attacks instead send requests that are expensive to serve, and these can be countered partly by rate limiting. *Mitigation:* upstream traffic filtering and scrubbing from a provider, which is the only effective defense against volumetric floods; rate limiting and request-cost controls, which address application-layer abuse but do not stop a flood that saturates the link; redundant capacity; and an incident plan that includes contacting the provider quickly.

### Network and Application Security

Defense begins with reducing what an attacker can reach. A **firewall** enforces rules about which traffic may enter or leave a network. **Segmentation** divides a network into zones, such as separating payment systems from office workstations, so that a compromise in one zone does not automatically expose the others. Think of it as watertight compartments in a ship: one breach should flood one compartment, not the vessel.

**TLS (Transport Layer Security)** protects data in transit. It encrypts the connection between client and server, verifies that the server is who it claims to be through its certificate, and detects tampering. Any service that carries credentials or personal data should require TLS, and plain HTTP should redirect or be refused.

Application security addresses the software itself. The **OWASP Top 10** is a widely used list of the most critical web application risks, maintained by the Open Web Application Security Project. It works best as a checklist: for each category (such as broken access control, injection, cryptographic failures, and security misconfiguration), ask whether your application has been tested against it. The list is revised periodically, so check the current version rather than relying on memory.

Application security also extends to the components an application is built from. Third-party libraries, container base images, and build tools all run with the application's trust, so the supply-chain risks described under Malware apply here as well. Dependency scanning and reviewing what a project pulls in are part of application security, not only the code written in-house.

### Identity and Access Management

Most breaches involve a compromised identity somewhere in the chain. **Identity and access management (IAM)** asks two questions: *who is this?* and *what may they do?*

**Authentication factors** are grouped into three categories: something you *know* (a password), something you *have* (a phone or hardware token), and something you *are* (a fingerprint). **Multi-factor authentication (MFA)** requires at least two different categories, so that a password alone is not enough. The factors must be genuinely independent. SMS codes are weaker than an authenticator app or hardware key because the phone number they travel to can be hijacked: in a **SIM swap**, an attacker persuades a mobile carrier to transfer the victim's number to a SIM the attacker controls, and then receives the codes. The phone is therefore not a fully independent factor when its number can be taken over.

**Passwords versus passkeys.** Passwords are shared secrets that the server must store (in hashed form) and that users must invent, reuse, and remember. They are vulnerable to phishing, because a user can be tricked into typing one into a fake site. **Passkeys** replace the shared secret with public-key cryptography: the device holds a private key that never leaves it, and signs a challenge from the genuine site. A passkey bound to a domain cannot be replayed on a look-alike site, which removes credential phishing against the passkey itself. Passkeys do not remove phishing in general. Attackers can still use adversary-in-the-middle proxies to relay a live session and hijack it after login, which passkeys reduce but do not eliminate, and account recovery paths (such as a helpdesk reset or a fallback email code) can still be phished. Passkeys are not yet universal, so where passwords remain, pair them with MFA.

**Role-based access control (RBAC)** groups permissions into roles (such as *billing clerk* or *database administrator*) and assigns users to roles rather than granting permissions one by one. Combined with least privilege, RBAC keeps access manageable: a new hire receives the role's permissions, and the role can be reviewed as a unit. Regular access reviews remove permissions that people no longer need, since access tends to accumulate over time.

### Cryptography in Practice

Cryptography is the mathematics that makes confidentiality, integrity, and authentication possible. You do not need to derive it, but you do need to know which tool solves which problem.

- **Symmetric encryption** uses one shared key for both encrypting and decrypting. It is fast and suits bulk data, such as an encrypted disk or a stored file. The challenge is distributing the key securely. AES is the standard choice.
- **Asymmetric encryption** uses a key pair: a public key anyone can see and a private key only the owner holds. It solves key distribution and underpins TLS handshakes and digital signatures, but it is much slower, so it is typically used to exchange a symmetric key rather than to encrypt bulk data.
- **Hashing** produces a fixed-length fingerprint of data. A good cryptographic hash is one-way and collision-resistant, so the same input always gives the same output and changes to the input are detectable. Hashing is used for two distinct purposes that should not be confused. The first is **password storage**: the system stores a hash rather than the password itself, so that a stolen database does not reveal the passwords directly. Because the hash is one-way, recovery is harder, but it is not impossible for weak passwords, since fast hashes can be guessed at enormous speed. Passwords therefore need a deliberately slow, salted algorithm such as Argon2, bcrypt, or scrypt. The second purpose is **integrity checking**, such as verifying a downloaded file against a published checksum. Hashing does not protect data at rest in general; that job belongs to encryption, which makes stored data unreadable without the key.
- **Digital signatures** combine hashing with asymmetric keys. The signer hashes a document and signs that hash with a private key; anyone with the matching public key can verify that the document is authentic and unchanged. (Signing schemes such as ECDSA, Ed25519, and RSA-PSS are defined in terms of signing operations, so "encrypting the hash" is a common simplification of what happens.) Code signing and software updates rely on this.

**Use vetted libraries, never custom schemes.** Cryptography is unforgiving: a subtle error in a mode of operation, random number generator, or comparison function can silently destroy security while the code appears to work. Inventing your own algorithm, or combining primitives by hand, is one of the most common and most dangerous mistakes in software. Use well-reviewed libraries and high-level APIs in your language (such as libsodium or the platform's standard crypto module), and configure them with current recommended settings.

### Detection and Response

Prevention will eventually fail, so mature security programs assume that breaches happen and focus on finding them quickly. Two capabilities make this possible.

**Logging and monitoring** record what happens in systems: logins, permission changes, file access, and network connections. Logs are useful only when four conditions hold. They must be **centralized**, collected from each system into a store that the system's own users and administrators cannot quietly edit. They must be **tamper-protected**, so that an attacker who gains access to a host cannot erase the record of their own actions. They must be **retained** long enough to investigate incidents that are discovered weeks or months after they occur. And they must be **reviewed or alerted on**, because logs that nobody examines provide no detection at all.

**Intrusion detection** systems watch for suspicious activity, either by matching known attack signatures or by flagging deviations from normal behavior, such as a service account suddenly logging in from another continent at 3 a.m.

**Incident response** is the structured process for handling a security event. The widely used framework, described in NIST Special Publication 800-61 (*Computer Security Incident Handling Guide*), has six phases:

1. **Preparation:** writing the plan, assigning roles, establishing contacts, and ensuring logging and backups are in place before anything happens.
2. **Detection and analysis:** determining whether an alert is a real incident, its scope, and its severity.
3. **Containment:** limiting the damage, for example by isolating an infected host or disabling a compromised account, while preserving evidence.
4. **Eradication:** removing the attacker's access and artifacts, including persistence mechanisms.
5. **Recovery:** restoring systems to normal operation, verifying they are clean, and monitoring closely for reinfection.
6. **Lessons learned:** reviewing what happened, how it was found, and what should change, so the next incident is handled better.

The final phase is the most often skipped, and it is where a single incident becomes lasting improvement.

### Human Factors and Security Culture

Technology cannot compensate for habits that undermine it. Security culture is the set of everyday practices that either support or erode the controls described above.

**Security awareness training** should be practical and recurring rather than a single annual video. Its most effective content is concrete: how to spot the phishing message in front of you, how to report a suspected mistake quickly without fear of blame, and why an urgent request for a password is always suspicious.

**Patching discipline** closes known vulnerabilities before attackers use them. Many major breaches exploited flaws for which fixes had already been released. A patching process should define timelines by severity, test updates where feasible, and track exceptions that cannot be patched promptly, along with compensating controls for them.

**Secure development practices** build security into software rather than adding it afterwards:
- **Threat modeling** asks, before or during design, what the system is, what it protects, who might attack it, and how. Structured methods such as STRIDE categorize threats (spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege). A simple exercise is to draw the data flows of a small application, mark each point where trust changes (such as where a user's input enters the server), and ask what could go wrong at each boundary. The output is a prioritized list of weaknesses, ranked by likelihood and impact, that tells the team where to spend effort first.
- **Code review** with a security lens catches flaws that automated tools miss, such as an authorization check that is present for one endpoint but absent from another.
- **Secrets management** keeps passwords, API keys, and certificates out of source code and configuration files, where they are easily leaked through version control. Secrets belong in dedicated vaults, injected at runtime, and rotated on a schedule and immediately after any suspected exposure.

Taken together, these practices show that cybersecurity is less a single barrier than a continuing cycle: prevent what can be prevented, detect what gets through, respond quickly, and learn from every event. The attacker needs only one lapse. The defender must make sure that lapses are rare, contained, and quickly noticed.