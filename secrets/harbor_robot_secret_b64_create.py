import json
import base64
import sys
import os

def generate_dockerconfig_base64(robot_file_path, registry_url):
    """
    Lit un fichier JSON contenant les informations d'un compte robot Harbor,
    et génère la chaîne encodée en Base64 pour un secret Kubernetes
    de type kubernetes.io/dockerconfigjson.

    Args:
        robot_file_path (str): Le chemin vers le fichier robot.json.
        registry_url (str): L'URL du registre Harbor.

    Returns:
        str: La chaîne encodée en Base64 pour le champ .dockerconfigjson,
             ou None en cas d'erreur.
    """
    try:
        # --- 1. Lire et parser le fichier JSON d'entrée ---
        if not os.path.exists(robot_file_path):
            print(f"Erreur : Le fichier '{robot_file_path}' n'a pas été trouvé.", file=sys.stderr)
            return None

        with open(robot_file_path, 'r') as f:
            robot_data = json.load(f)

        # --- 2. Extraire les informations nécessaires ---
        username = robot_data.get('name')
        password = robot_data.get('secret') # Le token du robot

        if not username or not password:
            print("Erreur : Le fichier JSON doit contenir les clés 'name' et 'secret'.", file=sys.stderr)
            return None

        # --- 3. Calculer le champ 'auth' (username:password encodé en base64) ---
        auth_string = f"{username}:{password}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64_bytes = base64.b64encode(auth_bytes)
        auth_b64_string = auth_b64_bytes.decode('utf-8')

        # --- 4. Construire la structure JSON .dockerconfigjson ---
        docker_config_dict = {
            "auths": {
                registry_url: {
                    "username": username,
                    "password": password,
                    "auth": auth_b64_string
                }
            }
        }

        # --- 5. Convertir le dictionnaire en chaîne JSON compacte ---
        # Utiliser separators pour éviter les espaces inutiles
        docker_config_json_string = json.dumps(docker_config_dict, separators=(',', ':'))

        # --- 6. Encoder la chaîne JSON complète en Base64 ---
        docker_config_json_bytes = docker_config_json_string.encode('utf-8')
        final_b64_bytes = base64.b64encode(docker_config_json_bytes)
        final_b64_string = final_b64_bytes.decode('utf-8')

        return final_b64_string

    except json.JSONDecodeError:
        print(f"Erreur : Le fichier '{robot_file_path}' n'est pas un JSON valide.", file=sys.stderr)
        return None
    except KeyError as e:
        print(f"Erreur : Clé manquante dans le JSON : {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Une erreur inattendue est survenue : {e}", file=sys.stderr)
        return None

if __name__ == "__main__":

    robot_file = "secrets/clear/robot$cluster-cd.json"
    harbor_registry = "harbor.cagou.ovh" 

    print(f"Lecture du fichier : {robot_file}")
    print(f"Utilisation du registre : {harbor_registry}")

    dockerconfig_b64 = generate_dockerconfig_base64(robot_file, harbor_registry)

    # --- Affichage du résultat ---
    if dockerconfig_b64:
        print("\n--- Secret .dockerconfigjson encodé en Base64 ---")
        print(dockerconfig_b64)
        print("\nCopiez cette chaîne et collez-la dans le champ 'data/.dockerconfigjson' de votre Secret Kubernetes (ou SealedSecret).")
    else:
        sys.exit(1) 