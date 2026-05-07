def call(Map cfg) {
    def rg    = cfg.rg
    def app   = cfg.app
    def image = cfg.image

    withCredentials([
        azureServicePrincipal('azure-sp')
    ]) {
        sh """
            set -euo pipefail
            az login --service-principal -u \$AZURE_CLIENT_ID \
                -p \$AZURE_CLIENT_SECRET --tenant \$AZURE_TENANT_ID >/dev/null
            az account set --subscription \$AZURE_SUBSCRIPTION_ID

            az containerapp update \
                --name ${app} --resource-group ${rg} \
                --image ${image} >/dev/null

            FQDN=\$(az containerapp show --name ${app} --resource-group ${rg} \
                --query properties.configuration.ingress.fqdn -o tsv)
            echo "AZURE_FQDN=\$FQDN"
        """
    }
}
