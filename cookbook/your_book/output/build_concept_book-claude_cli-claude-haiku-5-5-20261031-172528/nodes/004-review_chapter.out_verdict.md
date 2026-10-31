REVISION_NEEDED
1. **Factual error in NIST CSF 2.0 description.** The chapter says CSF 2.0 "adds Govern... to the original five" and lists the five. That is accurate, but it should note that Govern is a cross-cutting function, not a sequential step. As written it reads as a sixth phase in the lifecycle, which is misleading.

2. **Hashing section, "practically impossible to reverse."** Hashes are not reversible in the sense of recovering the input, but this phrasing conflates one-wayness with resistance to brute-force guessing of short or predictable inputs. Clarify that hashes of low-entropy inputs (short passwords, common files) can be guessed by hashing candidates, which is why password storage needs salting and slow functions.

3. **Hashing section, "Hashes are not a safe way to store passwords by themselves."** Correct, but the reason should be stated: fast hashes allow billions of guesses per second on GPUs. Without this, the reader cannot see why "slow" matters.

4. **Digital signatures section.** "Encrypts that hash with their private key" is a simplification. Modern signatures (e.g., RSA-PSS, ECDSA, Ed25519) do not use encryption-decryption in the RSA sense. Add a note that this describes the conceptual model, or use "signs the hash" to avoid implying a specific algorithm.

5. **Asymmetric encryption, "RSA and elliptic-curve methods (ECC)."** Fine, but ECC is a family, not a method comparable to RSA. Minor, but "RSA and elliptic-curve cryptography (ECC)" is more precise.

6. **Threat actors, "Insiders."** The chapter says insiders are "dangerous because their access already looks normal." Good point, but it should connect to least privilege and separation of duties, which appear later, so readers see the link.

7. **Attack surface section.** The phrase "anything you do not need, do not run" is clear, but it is the only place the chapter gives an action rule. Consider a short line that ties this to the risk equation (reducing surface lowers the likelihood term).

8. **Authentication, "Something you are."** This is the inherence factor. Some sources also name "somewhere you are" and "something you do" as additional factors. A brief note that the three categories are the traditional set would prevent confusion with newer taxonomies.

9. **Passkeys.** The chapter says phishing-resistant methods "bind the credential to the legitimate website." This is accurate for FIDO2/WebAuthn but should name the standard or say "FIDO2-based methods" so readers can look it up.

10. **Key Takeaways, "Frameworks."** The takeaway omits the caveat that CSF is not a certification, which the body states. Restate it, since it is the most common misunderstanding.

11. **Completeness.** The chapter does not define "non-repudiation" before using it in the signatures section, or explain "salted." Both need a one-line definition on first use.

12. **Closing paragraph, "ask which property it threatens..."** Useful, but it presumes the next chapter covers attacks in this framing. Confirm that chapter 2 is structured this way, or soften to "when you meet an attack, ask..."