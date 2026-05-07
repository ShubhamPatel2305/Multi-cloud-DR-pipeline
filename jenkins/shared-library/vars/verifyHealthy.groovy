def call(Map cfg) {
    def albVar = cfg.albVar
    def minTargets = cfg.minHealthyTargets ?: 1

    sh """
        set -euo pipefail
        url=\$(eval echo \\\$${albVar})
        if [ -z "\$url" ]; then
            echo "no ALB resolved for ${albVar}" >&2; exit 1
        fi

        echo "→ Probing \$url/health/deep until ${minTargets} consecutive 200s"
        ok=0
        for i in \$(seq 1 30); do
            code=\$(curl -s -o /dev/null -w '%{http_code}' "\$url/health/deep" || echo 000)
            if [ "\$code" = "200" ]; then
                ok=\$((ok+1))
                if [ \$ok -ge ${minTargets} ]; then
                    echo "→ Healthy"; exit 0
                fi
            else
                ok=0
                echo "  attempt \$i: \$code"
            fi
            sleep 5
        done
        echo "Health verification timed out for \$url" >&2
        exit 1
    """
}
