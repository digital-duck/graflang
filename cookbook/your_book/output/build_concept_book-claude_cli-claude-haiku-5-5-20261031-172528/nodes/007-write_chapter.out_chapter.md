## Chapter 1: Foundations of Cybersecurity

Cybersecurity is the practice of protecting information and the systems that store, process, and transmit it. It sounds simple, but the field rests on a handful of ideas that repeat across every tool, standard, and attack you will meet. This chapter introduces those foundations: the goals security serves, the vocabulary practitioners use, the adversaries they face, and the principles and techniques that make defense workable.

### The CIA Triad

Nearly every security decision can be traced back to three goals, collectively called the **CIA triad**:

- **Confidentiality** means information is seen only by those authorized to see it. A stolen customer database violates confidentiality.
- **Integrity** means information is accurate and unaltered except by authorized changes. A tampered payroll record that quietly raises someone's salary violates integrity.
- **Availability** means systems and data are accessible when needed. A website knocked offline by a flood of traffic violates availability.

The three properties often pull against each other. Encrypting data strengthens confidentiality but, if the key is lost, can destroy availability. Strict verification before every change protects integrity but slows legitimate work. Aggressive lockdowns can make a system so cumbersome that people route around it. Good security design makes these trade-offs explicit rather than pretending all three can be maximized at once.

Consider a hospital's patient records system. A ransomware attack that encrypts the records attacks availability, because doctors cannot read them. If attackers copy the records before encrypting them, they also breach confidentiality. If they alter a medication dosage in the database, they damage integrity, which may be the most dangerous outcome of all. One incident can hit all three properties, and a response plan must consider each.

### Core Terminology

Security discussions use precise words, and mixing them up leads to muddled thinking. Five terms matter most:

- A **threat** is anything that could cause harm: a criminal group, a natural disaster, a careless employee.
- A **vulnerability** is a weakness that a threat could exploit: an unpatched server, a password reused across accounts, a missing input check.
- A **risk** is the likelihood that a threat exploits a vulnerability, multiplied by the impact if it does. Risk is what you actually manage.
- An **exploit** is the method or code that takes advantage of a vulnerability.
- A **control** (also called a countermeasure or safeguard) is something that reduces risk: a firewall, an access review, a training program.

A concrete example ties these together. An employee laptop runs an outdated browser (vulnerability). A criminal group (threat) uses a known exploit to run code when the employee visits a malicious page. The risk is high if the laptop holds sensitive data and the browser is widely targeted. Installing automatic updates is a control that reduces the risk. Note that the vulnerability exists whether or not anyone attacks it; the threat is what makes it dangerous.

### Who Attacks, and Why

Threat actors differ in capability, patience, and motive, and that difference shapes what defenses matter.

- **Nation-states** conduct espionage, sabotage, and influence operations. They are well funded and patient, and they may spend months inside a network before acting.
- **Criminal groups** seek profit, through ransomware, fraud, theft of payment data, or resale of stolen credentials. Many operate like businesses, with specialists for initial access, extortion, and laundering.
- **Hacktivists** act for political or social causes, often through defacement, leaks, or disruptive attacks. Their capabilities vary widely.
- **Insiders** are people with legitimate access who misuse it, whether out of malice, for personal gain, or through carelessness. Insiders are dangerous precisely because their activity can look normal.
- **Opportunistic attackers** are not targeting you specifically. They scan the internet for weak systems and exploit whatever they find. Much real-world harm comes from this category, because automated tools make it cheap to attack everyone at once.

Understanding motivation helps prioritize. A small business is unlikely to be the target of a state-sponsored operation, but it is very likely to face opportunistic scanning and phishing. Defense should match the threats most likely to appear.

### Reducing the Attack Surface

The **attack surface** is the total set of points where an unauthorized user could try to enter or extract data: open network ports, web forms, APIs, user accounts, physical access points, and even employees who can be persuaded to click a link. Every component adds to the surface.

The principle of **attack surface reduction** says the safest feature is often the one you turn off. A server running services nobody uses offers attackers extra doors. Removing unused software, closing unneeded ports, disabling default accounts, and limiting who can reach an administrative interface all shrink the surface. Fewer moving parts mean fewer things that can go wrong, and fewer things to patch.

### Defense in Depth

No single control is perfect. Firewalls get misconfigured, passwords get phished, and software has bugs. **Defense in depth** responds to this reality by layering several independent controls so that one failure does not lead directly to disaster.

A building offers a useful picture. It may have a fence, a locked entrance, a receptionist who checks visitors, locked interior doors, and a safe for valuables. A thief who defeats the fence still faces the lock. In digital systems, the layers might include network segmentation, endpoint protection, strong authentication, encryption of stored data, and monitoring that detects unusual behavior. The goal is not that every layer is unbreakable, but that an attacker must defeat several of them, each taking time and creating chances for detection.

### Least Privilege and Separation of Duties

**Least privilege** means every user, program, and process gets only the access it needs to do its job, and no more. A payroll clerk does not need administrator rights on the domain controller. A web application's database account should be able to read and write its own tables, not drop the whole database. When an attacker compromises an account with limited rights, the damage it can do is limited too.

**Separation of duties** complements this by splitting critical tasks among people so that no single person can complete a sensitive operation alone. The employee who requests a vendor payment should not be the same person who approves it. This arrangement makes fraud harder, because it requires collusion, and it makes honest mistakes easier to catch.

### Basic Cryptography

Cryptography provides much of the technical foundation for confidentiality and integrity. Three ideas cover most of what you will encounter.

**Symmetric encryption** uses the same secret key to encrypt and decrypt data. It is fast and suitable for bulk data such as files or disk contents. Its weakness is key distribution: both parties must somehow share the key securely. The Advanced Encryption Standard (AES) is the widely used modern example.

**Asymmetric encryption** uses a pair of mathematically linked keys: a public key that anyone can have, and a private key that only its owner holds. Data encrypted with the public key can be decrypted only with the private key. This solves the key-sharing problem and underlies protocols such as TLS, which secures most web traffic. Asymmetric operations are slower, so systems typically use them to exchange a symmetric key, then encrypt the bulk data with that key.

**Hashing** transforms data into a fixed-length fingerprint. A good cryptographic hash, such as SHA-256, is easy to compute but practically impossible to reverse, and changing even one character of the input produces a completely different output. Hashes verify integrity: if the hash of a downloaded file matches the published value, the file was not altered in transit. Hashes also store passwords safely, though they must be combined with a salt and a deliberately slow function such as bcrypt or Argon2.

**Digital signatures** combine hashing and asymmetric keys to provide integrity, authenticity, and non-repudiation. The signer hashes a document and encrypts that hash with a private key. Anyone holding the matching public key can verify that the document came from the key's owner and was not changed afterward. Software vendors use signatures this way, so that your operating system can confirm an update is genuine.

A common misconception is that encryption alone makes a system secure. Encryption protects data only as well as its keys are protected, and it does nothing against an attacker who can already read the data after decryption.

### Authentication and the Limits of Passwords

Authentication answers the question "Are you who you say you are?" It is usually built from **factors**: something you know (a password), something you have (a phone or hardware token), and something you are (a fingerprint or face). Requiring two or more different types of factor is called multi-factor authentication, and it substantially raises the cost of account takeover, because stealing a password alone is no longer enough.

Passwords remain the most common factor, and they have serious limits. People reuse them across sites, so a breach at one service exposes others. They are easy to phish, guess, or capture from keystrokes. Password policies that demand frequent changes often lead to predictable patterns. Where possible, pair passwords with a second factor, use a password manager to generate and store unique credentials, and favor phishing-resistant methods such as hardware security keys or passkeys.

### Security Frameworks and Standards

Organizations rarely invent their security programs from scratch. Frameworks provide shared vocabulary, checklists, and structures that help teams plan and communicate with auditors, customers, and regulators.

The **NIST Cybersecurity Framework (CSF)**, published by the U.S. National Institute of Standards and Technology, organizes security activities into functions: Govern, Identify, Protect, Detect, Respond, and Recover. It is voluntary and flexible, and it is often used as a common language across industries. In version 2.0 it added an explicit Govern function covering risk strategy and oversight.

**ISO/IEC 27001** is an international standard for an information security management system (ISMS). Unlike NIST CSF's guidance, it defines requirements an organization can be certified against. It asks the organization to identify its information assets, assess risks, select controls, and continuously review its performance. The companion standard ISO/IEC 27002 describes recommended controls in detail.

Other frameworks, such as the CIS Critical Security Controls, offer prioritized, practical actions, and sector rules such as HIPAA for healthcare or PCI DSS for payment card data add legal or contractual obligations. A useful habit is to know which framework fits your situation and to treat frameworks as tools for thinking, not as ends in themselves. Passing an audit does not guarantee security, but a well-applied framework helps ensure that important questions get asked.

### Putting It Together

The ideas in this chapter form a single way of thinking. Start with the goals of the CIA triad. Identify threats and the vulnerabilities they might exploit, and weigh the resulting risk. Shrink the attack surface, layer controls, and grant only the access people need. Use cryptography to protect data in transit and at rest, and authenticate with more than a password. Anchor the whole program in a framework that keeps it organized and reviewable. Every later topic in this book, from common attacks to incident response, builds on these foundations.