# Hardware Integration Guide

## Android StrongBox / Keystore

### Requirements
- Android 9.0+ (API 28)
- Device with StrongBox support (Keymaster 4+)
- `android.hardware.keystore.strongbox` feature

### Key Generation (Kotlin)
```kotlin
val keyGen = KeyPairGenerator.getInstance(
    KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore"
)
val spec = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN)
    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
    .setDigests(KeyProperties.DIGEST_SHA256)
    .setUserAuthenticationRequired(true)
    .setUserAuthenticationValidityDurationSeconds(0) // Auth per use
    .setStrongBoxBacked(true) // Require StrongBox
    .setAttestationChallenge(challenge)
    .build()
keyGen.initialize(spec)
keyGen.generateKeyPair()
```

### Signing with BiometricPrompt
```kotlin
val prompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
        val cryptoObject = result.cryptoObject as BiometricPrompt.CryptoObject
        val signature = cryptoObject.signature
        signature.initSign(privateKey)
        signature.update(payload)
        val sigBytes = signature.sign()
        // Send sigBytes to server
    }
})
prompt.authenticate(promptInfo, BiometricPrompt.CryptoObject(signature))
```

### Attestation Verification (Server)
```python
def verify_android_attestation(cert_chain: list[bytes]) -> bool:
    # 1. Verify chain to Google root
    # 2. Parse attestation extension (OID 1.3.6.1.4.1.11129.2.1.17)
    # 3. Check:
    #    - securityLevel == "StrongBox"
    #    - verifiedBootState == "Verified"
    #    - deviceLocked == true
    #    - keyAlgorithm == "EC"
    #    - keySize == 256
    return True
```

---

## iOS Secure Enclave

### Requirements
- iOS 13+ / macOS 10.15+
- Secure Enclave (A7+ / T1/T2/M1)
- FaceID/TouchID enrolled

### Key Generation (Swift)
```swift
let accessControl = SecAccessControlCreateWithFlags(
    kCFAllocatorDefault,
    kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
    [.userPresence, .biometryCurrentSet], // Require FaceID/TouchID
    nil
)

let attributes: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256,
    kSecPrivateKeyAttrs as String: [
        kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
        kSecAttrAccessControl as String: accessControl,
        kSecAttrApplicationTag as String: "com.cancelablebio.auth.devicekey",
    ],
]

var error: Unmanaged<CFError>?
guard let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &error) else {
    throw error!.takeRetainedValue() as Error
}
```

### Signing with LocalAuthentication
```swift
let context = LAContext()
context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Authenticate to sign") { success, error in
    if success {
        let algorithm = SecKeyAlgorithm.ecdsaSignatureMessageX962SHA256
        var error: Unmanaged<CFError>?
        guard let signature = SecKeyCreateSignature(privateKey, algorithm, payload, &error) else {
            return
        }
        // Send signature to server
    }
}
```

---

## OP-TEE Trusted Application

### Build Environment
```bash
git clone https://github.com/OP-TEE/build.git
cd build
make toolchains
```

### TA Structure (C)
```c
// ta/bioauth_ta.c
#include <tee_internal_api.h>
#include <bioauth_ta.h>

TEE_Result TA_InvokeCommandEntryPoint(
    void *session_id,
    uint32_t cmd_id,
    uint32_t param_types,
    TEE_Param params[4]
) {
    switch (cmd_id) {
        case TA_BIOAUTH_CMD_VERIFY_AND_SIGN:
            return verify_and_sign(params);
        default:
            return TEE_ERROR_BAD_PARAMETERS;
    }
}

static TEE_Result verify_and_sign(TEE_Param params[4]) {
    // 1. Unseal HE secret key
    // 2. Decrypt similarity (call HE lib)
    // 3. Check threshold
    // 4. Check nonce (monotonic time + secure storage)
    // 5. Check key version (secure storage)
    // 6. Sign payload with device key
    // 7. Return signature
}
```

### Client App (Normal World)
```c
TEEC_Operation op = {0};
op.paramTypes = TEEC_PARAM_TYPES(
    TEEC_MEMREF_TEMP_INOUT,  // encrypted_similarity
    TEEC_MEMREF_TEMP_INOUT,  // he_secret_key
    TEEC_MEMREF_TEMP_INOUT,  // nonce
    TEEC_VALUE_INOUT         // key_version, threshold
);
TEEC_InvokeCommand(&session, TA_BIOAUTH_CMD_VERIFY_AND_SIGN, &op, &origin);
```
