function bufferDecode(value) {
    return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
}

function bufferEncode(value) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(value)))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=/g, "");
}

async function registerFingerprint() {
    // Tout votre code avec await doit rester ICI, entre les accolades
    const response = await fetch('/webauthn/register/options');
    const options = await response.json();

    options.challenge = bufferDecode(options.challenge);
    options.user.id = bufferDecode(options.user.id);

    const credential = await navigator.credentials.create({ publicKey: options });

    const body = {
        id: credential.id,
        rawId: bufferEncode(credential.rawId),
        type: credential.type,
        response: {
            attestationObject: bufferEncode(credential.response.attestationObject),
            clientDataJSON: bufferEncode(credential.response.clientDataJSON),
        },
    };

    const verifyRes = await fetch('/webauthn/register/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
});

const result = await verifyRes.json();
    if (result.status === 'ok') {
        // Redirection vers la route définie dans app.py
        window.location.href = "/auth-success";
    } else {
        alert("Erreur : " + result.message);
    }
}
// NE RIEN AJOUTER APRÈS CETTE LIGNE QUI UTILISE AWAIT