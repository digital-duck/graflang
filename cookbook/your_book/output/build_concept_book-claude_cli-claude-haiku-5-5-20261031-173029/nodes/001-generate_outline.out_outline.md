# Concept Book Outline: Cybersecurity

## Chapter 1: Foundations of Cybersecurity

**Key Concepts**
- **The CIA triad:** confidentiality, integrity, and availability as the core goals that security controls protect.
- **Threats, vulnerabilities, and risk:** how they differ, and how risk is estimated as likelihood × impact.
- **Threat actors:** nation-states, organized crime, hacktivists, insiders, and opportunistic attackers, and their motivations.
- **Attack surfaces and the attack lifecycle:** reconnaissance, initial access, persistence, privilege escalation, lateral movement, and exfiltration.
- **Defense in depth and least privilege:** layering controls so no single failure is catastrophic, and granting only the access that is needed.
- **Security frameworks and governance:** the role of policies, standards (e.g., NIST CSF, ISO/IEC 27001), and compliance in organizing security work.

**Learning Objectives**
- Explain the CIA triad and give an example of a control that protects each property.
- Distinguish between threats, vulnerabilities, and risks, and apply a basic risk assessment to a simple system.
- Describe the common stages of an attack lifecycle and identify where defenders can interrupt it.
- Justify the use of defense in depth and least privilege in a realistic scenario.
- Identify the major threat actor categories and the kinds of targets each tends to pursue.

## Chapter 2: Threats, Defenses, and Secure Practice

**Key Concepts**
- **Common attack techniques:** phishing and social engineering, malware (ransomware, trojans, worms), injection attacks (e.g., SQL injection, XSS), credential attacks, and denial of service.
- **Network and application security:** firewalls, segmentation, TLS, and the OWASP Top 10 as a checklist for web application risks.
- **Identity and access management:** authentication factors, passwords versus passkeys, multi-factor authentication, and role-based access control.
- **Cryptography in practice:** symmetric versus asymmetric encryption, hashing, digital signatures, and the importance of using vetted libraries rather than custom schemes.
- **Detection and response:** logging, monitoring, intrusion detection, incident response phases (preparation, detection, containment, eradication, recovery, lessons learned).
- **Human factors and security culture:** security awareness training, patching discipline, and secure development practices (threat modeling, code review, secrets management).

**Learning Objectives**
- Recognize common attack techniques and describe a control that mitigates each one.
- Explain how TLS and hashing protect data in transit and at rest, and why custom cryptography should be avoided.
- Design a basic access control scheme using least privilege and multi-factor authentication.
- Outline the phases of an incident response plan and the role of logging in detection.
- Apply threat modeling to a small application to identify and prioritize security weaknesses.