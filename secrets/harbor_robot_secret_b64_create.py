import json
import base64
import sys
import os

def generate_dockerconfig_base64(robot_file_path, registry_url):
    """
    Lit un fichier JSON contenant les informations d'un compte robot Harbor,
    et génère la chaîne encodée en Base64 pour un secret Kubernetes
    de type kubernetes.io/dockerconfigjson.
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

def generate_secret_yaml(b64_content, secret_name, namespace):
    """Génère le contenu YAML d'un secret Kubernetes avec annotations Reflector."""
    yaml_template = f"""apiVersion: v1
kind: Secret
metadata:
  name: {secret_name}
  namespace: {namespace}
  annotations:
    reflector.v1.k8s.emberstack.com/reflection-allowed: "true"
    reflector.v1.k8s.emberstack.com/reflection-allowed-namespaces: ""
    reflector.v1.k8s.emberstack.com/reflection-auto-enabled: "true"
    reflector.v1.k8s.emberstack.com/reflection-auto-namespaces-selector: "replicate-harbor-cicd=true"
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: {b64_content}
"""
    return yaml_template

if __name__ == "__main__":
    # Paramètres par défaut
    robot_file = "secrets/clear/robot$sa-harbor-cicd.json"
    harbor_registry = "harbor.valab.top"
    secret_name = "harbor-cicd-secret"
    target_namespace = "storage" # Par défaut
    output_file = "secrets/clear/harbor-cicd-secret.yaml"

    print(f"Lecture du fichier : {robot_file}")
    print(f"Utilisation du registre : {harbor_registry}")

    dockerconfig_b64 = generate_dockerconfig_base64(robot_file, harbor_registry)

    if dockerconfig_b64:
        # Générer le YAML
        secret_yaml = generate_secret_yaml(dockerconfig_b64, secret_name, target_namespace)
        
        # Écrire le fichier dans secrets/clear/
        try:
            with open(output_file, 'w') as f:
                f.write(secret_yaml)
            print(f"\n✅ Secret YAML généré : {output_file}")
            print(f"   Namespace : {target_namespace} | Nom : {secret_name}")
            print(f"\nVous pouvez maintenant le 'sceller' avec kubeseal.")
        except Exception as e:
            print(f"Erreur lors de l'écriture : {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.exit(1)