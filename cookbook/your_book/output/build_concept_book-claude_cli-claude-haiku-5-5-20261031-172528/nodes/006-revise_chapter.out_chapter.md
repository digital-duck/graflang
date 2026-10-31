## Chapter 1: Foundations of Cybersecurity

Every security decision, from choosing a password to designing a national power grid's control network, rests on a small set of ideas. This chapter introduces them. Learn these first, and the later chapters on attacks, defenses, and incident response will read as applications of a few principles rather than a pile of unrelated facts.

### The CIA Triad

Security is about protecting information and the systems that handle it. Three properties define what "protected" means:

- **Confidentiality** means information is seen only by those authorized to see it.
- **Integrity** means information and systems are accurate and unaltered by unauthorized parties.
- **Availability** means authorized users can access information and systems when they need them.

Consider a hospital's patient records. If an outsider reads them, confidentiality has failed. If a nurse's medication dose is silently changed, integrity has failed. If the records system is down during an emergency, availability has failed. Each failure is a different kind of harm, and each calls for different controls.

The three properties often pull against each other. Encrypting data strongly protects confidentiality, but if the key is lost, availability suffers. Requiring several approvals before any change protects integrity, but it slows legitimate work. Replicating a database across many sites improves availability, but every copy is another place where confidentiality can leak. Good security design makes these trade-offs deliberately, based on what the data and the business actually need, rather than maximizing all three everywhere at once.

### Core Terminology

Four words are constantly confused, and the distinctions matter.

- A **threat** is anything that could cause harm: a criminal group, a flood, a careless employee.
- A **vulnerability** is a weakness that a threat could exploit: an unpatched server, a password that is reused across sites, a door that is propped open.
- A **risk** is the likelihood that a threat exploits a vulnerability, multiplied by the impact if it does. A vulnerability in a system nobody can reach carries little risk. The same vulnerability on an internet-facing payment server carries a great deal.
- An **exploit** is the method or code that takes advantage of a vulnerability. A "proof of concept" exploit demonstrates that a weakness is real.
- A **control** (also called a safeguard or countermeasure) is anything that reduces risk: a firewall, a policy, a lock, a training program.

Here is one concrete chain. A criminal group (threat) learns that a web server runs an outdated library with a known flaw (vulnerability). They publish a script that triggers the flaw (exploit). The company's customer database sits on that server with no segmentation, so a successful attack could expose millions of records (high impact). The company's response might be to apply the patch (control), limit what the web server can reach (control), and monitor for the exploit's signature (control). Residual risk is whatever remains after these controls, and managing it is the real work of security.

### Threat Actors

Not all attackers want the same thing or have the same capabilities. Understanding motivation helps predict behavior and prioritize defenses.

- **Nation-states** conduct espionage, sabotage, and influence operations. They are well funded and patient, and they may spend months inside a network before acting. Their targets include government, defense, energy, and critical infrastructure.
- **Criminal groups** want money. Ransomware gangs, fraud rings, and card-skimming operations are often organized like businesses, with specialists for initial access, extortion, and laundering.
- **Hacktivists** act for political or social causes. They tend to deface websites, leak documents, or disrupt services to draw attention. Their capabilities vary widely.
- **Insiders** are employees, contractors, or partners with legitimate access. They may be malicious, such as a departing employee taking customer lists, or negligent, such as one who emails a file to the wrong person. Insiders are dangerous because their access already looks normal. This is exactly why least privilege and separation of duties, covered later in this chapter, matter: they limit what any one insider's legitimate access can do.
- **Opportunistic attackers** are not targeting anyone in particular. They scan the internet for easy targets and exploit whatever they find. Many attacks that look targeted are actually opportunistic, and an organization with weak basics can be hit by them regardless of its size or industry.

### Attack Surfaces and Reducing Them

An **attack surface** is the total set of points where an attacker could try to enter or extract data: network services, web forms, APIs, employee accounts, email, physical doors, USB ports, third-party software. Every additional service, feature, or account adds to the surface.

The principle of **attack surface reduction** is simple: anything you do not need, do not run. Close unused network ports. Remove software that is no longer used. Disable default accounts. Retire old systems rather than leaving them online "just in case." This ties directly to the risk equation. Risk is likelihood times impact, and each vulnerability on the surface contributes to the likelihood term. Removing an unneeded service removes its vulnerabilities from the surface, lowering the likelihood that any threat succeeds, so there are fewer ways in that must all be defended.

### Defense in Depth

No single control is perfect. Firewalls get misconfigured, passwords get phished, and software has bugs. **Defense in depth** assumes that any one layer will eventually fail and places several independent layers between an attacker and the asset they want.

A typical layered design for a customer database might include a network firewall at the perimeter, network segmentation that isolates the database from the public web tier, authentication on the application, encryption of the data at rest, database-level permissions, and logging that alerts staff when unusual queries appear. An attacker who defeats the firewall still faces the other layers. Each layer buys time and creates another chance for detection.

The layers should be genuinely independent. Three firewalls from the same vendor with the same flaw are not three layers in any meaningful sense.

### Least Privilege and Separation of Duties

**Least privilege** means every user, program, and process receives only the access it needs to do its job, and no more. A payroll clerk does not need access to the source code repository. A backup service does not need administrator rights on every machine. When an account is compromised, least privilege limits the damage to what that account could already do.

**Separation of duties** means that no single person can complete a sensitive process alone. The person who requests a payment should not also be able to approve it. The developer who writes code should not be the only one who deploys it to production. Splitting critical actions across people makes fraud and mistakes harder, because an attacker or careless employee would need to deceive more than one party.

Both principles are cheap to adopt in design and expensive to retrofit, so they belong in the earliest stages of any system.

### Basic Cryptography

Cryptography provides tools for confidentiality, integrity, and authentication. You do not need to build cryptographic systems to use them well, but you do need to know what each tool does.

**Symmetric encryption** uses one shared secret key to both encrypt and decrypt. AES is the standard example. It is fast and suitable for large volumes of data. Its weakness is key distribution: both parties must somehow share the key securely beforehand.

**Asymmetric encryption** uses a key pair: a public key that anyone may hold and a private key that only its owner keeps. Data encrypted with the public key can be decrypted only with the private key. RSA and elliptic-curve cryptography (ECC) are common examples. ECC is a family of methods, not a single algorithm. Asymmetric methods solve the key-distribution problem but are slower, so in practice they are often used to exchange a symmetric key, which then encrypts the bulk of the traffic. This pattern is how HTTPS works.

**Hashing** converts data of any size into a fixed-length fingerprint. A good cryptographic hash, such as SHA-256, has three useful properties: it is easy to compute, it is one-way in the sense that the input cannot practically be recovered from the output, and it is practically impossible to find two inputs with the same hash. Hashes verify integrity: if a downloaded file's hash matches the publisher's published hash, the file was not altered in transit.

One-wayness does not protect low-entropy inputs. A short password or a common file can be recovered by hashing candidate values and comparing the results, so an attacker who has a hash of "password123" needs only to try likely guesses. This is why password storage needs two additional measures. A **salt**, a random value stored alongside the hash and combined with the password before hashing, ensures that identical passwords produce different hashes and that precomputed lookup tables cannot be reused across accounts. A **slow** password-hashing function such as bcrypt, scrypt, or Argon2 is deliberately expensive to compute. Fast hashes such as SHA-256 are designed for speed, and a modern GPU can compute billions of them per second, so a stolen database of fast-hashed passwords can be cracked quickly. A slow function limits an attacker to a far smaller number of guesses per second. Hashes are also not encryption: there is no key, and they do not hide data that must later be read back.

**Digital signatures** combine hashing and asymmetric keys. Conceptually, the signer computes a hash of the document and signs that hash with their private key. Anyone with the signer's public key can check the signature against the hash, recompute the hash from the document, and compare. A match proves two things: the document has not changed, and it was signed by the holder of the private key. Real schemes such as RSA-PSS, ECDSA, and Ed25519 are specific algorithms that do not literally "encrypt the hash" in the RSA encryption sense; the model here describes the principle, not the exact mathematics. Signatures provide integrity and authenticity, and, with proper key management, **non-repudiation**, meaning the signer cannot plausibly deny having signed.

### Authentication Factors and the Limits of Passwords

Authentication answers the question "Who are you?" The three traditional factor categories are:

- **Something you know**, such as a password or PIN
- **Something you have**, such as a phone, hardware security key, or smart card
- **Something you are**, such as a fingerprint or face

Some newer taxonomies add factors such as "somewhere you are" (location) or "something you do" (behavioral patterns). The three categories above are the traditional set, and they are the ones most standards and exams refer to.

Multi-factor authentication (MFA) requires two or more different categories. It matters because it defeats the most common attack: stealing a single password. An attacker with a phished password still cannot log in without the second factor.

Passwords are weak for predictable reasons. People reuse them across sites, so one breach unlocks many accounts. They are chosen to be memorable, which makes them guessable. They are easily captured by phishing pages that look like real login screens. Attackers also exploit password spraying, trying a few common passwords against many accounts to avoid lockouts. Passwords still have a role, but they should be long, unique, stored in a password manager, and paired with MFA wherever possible. Phishing-resistant methods go further. FIDO2 and WebAuthn-based methods, including hardware keys and passkeys, bind the credential to the legitimate website's origin, so it cannot be presented to a look-alike site, even if the user is fooled into visiting one.

### Security Frameworks and Standards

Security frameworks give organizations a shared vocabulary and a checklist of what a mature program should cover. Two widely used examples illustrate the range.

The **NIST Cybersecurity Framework (CSF)**, published by the U.S. National Institute of Standards and Technology, organizes security activities into functions. Version 2.0 (2024) adds **Govern** to the original five: **Identify**, **Protect**, **Detect**, **Respond**, and **Recover**. Govern is a cross-cutting function, not a sequential step. It covers the strategy, risk tolerance, and oversight that inform all the others, and it applies continuously rather than coming first or last. The other five are activities an organization carries on in parallel and repeatedly, not a linear pipeline. CSF is a voluntary, outcome-oriented guide, and it is often used to describe a program's current state and target state. It is not a certification.

**ISO/IEC 27001** is an international standard that specifies requirements for an Information Security Management System (ISMS): a systematic process for assessing risk and selecting controls, maintained over time. Organizations can be formally audited and certified against it. Its companion, ISO/IEC 27002, provides detailed guidance on the controls themselves.

The two serve different needs. CSF helps an organization think about and communicate its security posture. ISO 27001 provides a certifiable management system that customers and regulators can verify. Many organizations use both, along with sector-specific rules such as those for payment cards or health records.

### Key Takeaways

- Security protects **confidentiality, integrity, and availability**, and these properties often trade off against each other.
- **Risk** combines the likelihood of exploitation with its impact. Threats, vulnerabilities, exploits, and controls are the parts of that equation.
- Different **threat actors** have different motives, and effective defense starts with knowing which ones are likely.
- Reduce the **attack surface**, layer **defenses in depth**, and grant **least privilege** with **separation of duties**, so that no single failure is catastrophic. Reducing the surface lowers the likelihood term of the risk equation.
- **Symmetric** and **asymmetric** encryption, **hashing**, and **digital signatures** each solve a different problem. Knowing which one fits a situation is more important than knowing how they work internally.
- **Multi-factor authentication** defeats most credential theft. Passwords alone are not enough.
- **Frameworks** such as NIST CSF and ISO/IEC 27001 give structure to a security program and a common language for discussing it. CSF is a guide, not a certification; ISO/IEC 27001 is the standard that can be certified.

These foundations recur throughout the rest of this book. When you meet an attack, ask which property it threatens, which vulnerability it uses, and which layer should have stopped it.