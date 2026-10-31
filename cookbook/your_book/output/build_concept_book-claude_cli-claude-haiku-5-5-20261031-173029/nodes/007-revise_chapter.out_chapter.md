## Chapter 1: Foundations of Cybersecurity

Every security decision, from choosing a password policy to deciding whether to patch a server tonight, comes back to a handful of ideas. This chapter introduces them. Once you have them, the rest of the subject becomes much easier to navigate, because most specific tools and techniques are answers to a few basic questions: What are we protecting? Against whom? How much does it matter? And where can we stop an attack?

### The CIA Triad

Security begins with three goals, often called the **CIA triad**:

- **Confidentiality** means information is seen only by those authorized to see it. A hospital keeps patient records confidential by encrypting them at rest and restricting who can open the database.
- **Integrity** means information and systems are not changed in unauthorized or unnoticed ways. A bank protects integrity by using checksums on transaction records to catch accidental corruption, and digital signatures or keyed message authentication codes (MACs) to catch deliberate changes, since an attacker who alters a record could simply recompute a plain checksum.
- **Availability** means systems and data are accessible when needed. An online retailer protects availability with redundant servers and load balancers, so a traffic surge or hardware failure does not take the store offline.

These three properties are not the only ones. Many texts add **authenticity**, the assurance that a message or user is who they claim to be, and **accountability** (often called non-repudiation), the ability to show later who did what. Identity and access controls, discussed in later chapters, depend on both. The CIA triad remains the core vocabulary, and these extensions refine it rather than replace it.

The core three also pull against each other. Encrypting everything strengthens confidentiality but can make recovery harder if keys are lost, which hurts availability. Strict change controls protect integrity but can slow emergency fixes. Good security is the art of balancing them for a particular system, not maximizing one at the expense of the others.

### Threats, Vulnerabilities, and Risk

These three words are often used interchangeably, but they mean different things:

- A **vulnerability** is a weakness in a system: an unpatched library, a default password, a missing input check.
- A **threat** is anything that could exploit a vulnerability: a criminal group, a careless employee, a flood.
- A **risk** is the potential for harm when a threat meets a vulnerability.

A simple way to estimate risk is:

> **Risk ≈ Likelihood × Impact**

Consider a small company's customer database that is reachable from the internet and has an unpatched web framework (the vulnerability). Automated scanners constantly probe for that framework, so the likelihood of exploitation is high. The impact is also high, because the database holds personal data and a breach would bring legal and reputational damage. The risk is therefore high and deserves immediate attention. Compare that with an internal print server that is unpatched but unreachable from outside the building: the vulnerability is real, but the likelihood is lower and the impact is smaller, so the risk ranks lower.

Risk assessment is never precise. The value of the exercise is in forcing a team to list assets, identify what could go wrong, and rank the results so that limited time and money go where they matter most.

### Threat Actors

Not all attackers are alike. Their goals, resources, and patience differ, and so do the targets they choose.

- **Nation-states** have large budgets and long time horizons. They pursue espionage, intellectual property, and sometimes disruption of critical infrastructure such as power grids. Their intrusions can last months or years.
- **Organized crime** is motivated by profit. Ransomware gangs, fraud rings, and card-skimming operations pursue whatever yields money efficiently, including hospitals, municipalities, and small businesses that may pay quickly.
- **Hacktivists** act for political or social causes. Their typical tools are defacement, data leaks, and denial-of-service campaigns against organizations they oppose.
- **Insiders** are employees, contractors, or partners with legitimate access. They may be malicious, seeking revenge or profit, or simply careless. Insiders are dangerous because their actions can look like normal work.
- **Opportunistic attackers** scan broadly for any easy target. They often use public exploits with little customization, and their victims are whoever is exposed and unpatched enough to be found.

Understanding actors helps defenders prioritize. A bakery and a defense contractor face different adversaries, and a security program that ignores that difference will spend money on the wrong controls.

### Attack Surfaces and the Attack Lifecycle

An **attack surface** is the total set of points where an attacker could try to enter or extract data: public web pages, remote-access services, email, employee laptops, third-party integrations, even the physical building. Reducing the attack surface, by closing unused services or removing unnecessary features, is often the cheapest security improvement available.

Attacks often unfold in a sequence of stages. Describing this sequence, often called the **attack lifecycle**, helps defenders see where they can interrupt an intruder. The six stages below are a simplified model, not a standard fixed list. Real intrusions often skip, repeat, or reorder stages. Two widely used alternatives are the **Lockheed Martin Cyber Kill Chain**, which describes seven stages from reconnaissance through actions on objectives, and the **MITRE ATT&CK** knowledge base, which catalogs observed adversary tactics and techniques in detail. Readers who go on to threat intelligence or detection engineering will meet both.

The simplified model has six stages:

1. **Reconnaissance:** the attacker gathers information about the target, such as employee names, exposed services, and software versions.
2. **Initial access:** the attacker gets a first foothold, perhaps through a phishing email or a vulnerable public server.
3. **Persistence:** the attacker installs a way to return even if the first entry point is closed, such as a scheduled task or a stolen login.
4. **Privilege escalation:** the attacker turns a limited account into one with more power, such as administrator rights.
5. **Lateral movement:** the attacker moves through the network to other machines, looking for valuable systems.
6. **Exfiltration and impact:** the attacker copies data out of the organization. Many modern attacks steal data first and then use it as leverage. Ransomware adds an impact on top of this: the attacker encrypts systems and demands payment for the decryption key, and may threaten to publish the stolen data if the demand is refused. This double extortion pattern makes exfiltration and encryption two distinct harms.

Each stage offers a defensive opportunity. Hardening public services reduces initial access. Monitoring for unusual logins helps catch persistence. Restricting administrator rights limits escalation. Network segmentation slows lateral movement. Data-loss controls and egress monitoring make exfiltration harder to hide, and encrypted, offline backups limit the damage of ransomware. The earlier an intrusion is stopped, the less damage it can do, which is why defenders aim to break the chain as early as they can.

### Defense in Depth and Least Privilege

No control is perfect, so security relies on layers. **Defense in depth** means arranging several independent safeguards so that if one fails, another still stands between the attacker and the asset. A building might combine a locked door, an alarm system, a camera, and a locked server cabinet. A web application might combine a web application firewall, input validation, parameterized database queries, and a database account with limited permissions. An attacker who bypasses one layer must still defeat the others.

Layers only help if they are truly independent. Three firewalls from the same vendor with the same misconfiguration are one layer, not three.

**Least privilege** is the principle that every user, program, and process should receive only the access it needs to do its job, and no more. Consider a reporting service that reads sales data and writes summary files. If it runs with administrator rights, a single compromise gives the attacker full control of the server. If it runs with a dedicated account that can read one database schema and write to one folder, the same compromise is far less damaging. Least privilege also limits mistakes: a support technician who cannot delete production data cannot delete it by accident.

Defense in depth and least privilege reinforce each other. Least privilege shrinks what each layer must protect, and layering ensures that a single broken control does not expose everything.

### Security Frameworks and Governance

Security is not only a matter of technology. Organizations need shared language, documented decisions, and a way to show that their practices meet expectations. This is the role of **governance**.

- **Policies** state what the organization requires, for example that all remote access must use multi-factor authentication.
- **Standards** define how to meet those requirements in specific, measurable terms.
- **Frameworks** provide structured guidance for organizing the whole security program. The **NIST Cybersecurity Framework (CSF) 2.0**, published in 2024, organizes work into six functions: Govern, Identify, Protect, Detect, Respond, and Recover. Govern, which covers the organization's risk strategy, policies, and oversight, was added in version 2.0. **ISO/IEC 27001** specifies requirements for an information security management system and can be certified by external auditors.
- **Compliance** means meeting external obligations, such as data protection laws or industry rules for payment card data. Compliance sets a floor; it does not by itself guarantee security, but it gives organizations a structured reason to do the basics well.

Frameworks matter because they turn scattered technical tasks into a managed program. They help answer questions that otherwise go unasked: Who owns this risk? How do we know the control still works? What do we do when it fails?

### Putting It Together

Imagine a small clinic that stores patient records in a cloud system. Its CIA priorities are confidentiality (patient privacy), integrity (accurate medical records), and availability (doctors need records during appointments). Its main threats include ransomware gangs, which target healthcare organizations because they often pay quickly to restore patient care, and careless staff who might click a phishing link. Its vulnerabilities might include an unreviewed vendor integration and shared administrator accounts. Estimating risk, the clinic ranks shared administrator accounts as a high-priority fix: the likelihood of misuse is high and the impact on patient data is severe. It applies least privilege by giving each staff member a personal account with only the access their role requires. It applies defense in depth by combining multi-factor authentication, encrypted backups stored separately, and logging of record access. Finally, it adopts a policy requiring these controls and reviews them against a recognized framework.

Every concept in this chapter appears in that example. The rest of the subject builds on them: the techniques attackers use, the tools defenders deploy, and the practices that keep both working over time.