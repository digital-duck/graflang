REVISION_NEEDED

1. **Ransomware is placed in the wrong lifecycle stage.** The Exfiltration step says ransomware "encrypts it and demands payment." Encryption is the impact, not exfiltration, and modern ransomware often steals data first (double extortion). Move the encryption to a separate impact stage, or describe exfiltration as the stage where data leaves and ransomware as an impact on top of it.

2. **The checksum example overstates integrity protection.** "Checksums and digital signatures... so a tampered entry is detected" implies checksums catch deliberate tampering. A checksum only catches accidental corruption, because an attacker who alters a record can recompute it. Say that checksums catch accidental corruption and digital signatures (or keyed MACs) catch deliberate changes.

3. **The NIST CSF description is out of date.** CSF 2.0 (2024) added a Govern function, so the list should read Govern, Identify, Protect, Detect, Respond, Recover. Given the chapter's date, it should reflect the current version.

4. **The attack lifecycle is presented as the only model.** The six stages are a simplified sequence. The chapter should say so and point to a common alternative, such as the Cyber Kill Chain or MITRE ATT&CK, so readers know the stages are not a standard fixed list.

5. **"Its willingness to pay" is ambiguous.** In the clinic example it reads as if the clinic is willing to pay. It should say healthcare organizations' willingness to pay, or name the target explicitly.

6. **"Low-skill individuals" for opportunistic attackers is an unsupported generalization.** Say that they often use public exploits with little customization, and drop the claim about skill level, or qualify it.

7. **The discussion of the three CIA goals could note that they are not the only properties.** Authenticity and accountability (non-repudiation) are often added, and the chapter's later discussion of identity and least privilege relies on them. A short sentence acknowledging the extension would make the framing more complete.