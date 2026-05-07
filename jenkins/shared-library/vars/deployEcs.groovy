def call(Map cfg) {
    def region  = cfg.region
    def cluster = cfg.cluster
    def service = cfg.service
    def image   = cfg.image

    withCredentials([
        [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-deploy']
    ]) {
        sh """
            set -euo pipefail
            export AWS_DEFAULT_REGION=${region}

            echo '→ Fetching current task definition'
            CURRENT=\$(aws ecs describe-services --cluster ${cluster} --services ${service} \
                --query 'services[0].taskDefinition' --output text)

            aws ecs describe-task-definition --task-definition \$CURRENT \
                --query 'taskDefinition' \
                --output json > taskdef.json

            jq --arg img '${image}' '
                .containerDefinitions[0].image = \$img
                | del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
                      .compatibilities, .registeredAt, .registeredBy)
            ' taskdef.json > taskdef.new.json

            NEW=\$(aws ecs register-task-definition \
                --cli-input-json file://taskdef.new.json \
                --query 'taskDefinition.taskDefinitionArn' --output text)

            aws ecs update-service --cluster ${cluster} --service ${service} \
                --task-definition \$NEW --force-new-deployment >/dev/null

            echo '→ Waiting for deployment to stabilise'
            aws ecs wait services-stable --cluster ${cluster} --services ${service}

            ALB=\$(aws elbv2 describe-load-balancers \
                --query "LoadBalancers[?contains(LoadBalancerName,'${cluster.replace('-cluster', '-alb')}')].DNSName" \
                --output text | head -n1)
            echo "ALB=\$ALB"
        """
    }
}
