def call(Map cfg) {
    def routerUrl = cfg.routerUrl
    def target    = cfg.target

    sh """
        set -euo pipefail
        echo '→ Snapshot pool before drill'
        curl -fsS ${routerUrl}/admin/pool | jq

        echo '→ Inject failure on ${target}'
        TARGET_PORT=\$(case ${target} in
            aws-mumbai)       echo 8081 ;;
            aws-singapore)    echo 8082 ;;
            azure-secondary)  echo 8083 ;;
        esac)
        curl -fsS -X POST http://app-${target}:8080/admin/inject-failure \
            -H 'content-type: application/json' \
            -d '{"mode":"deep"}' | jq

        echo '→ Wait for router to detect outage'
        sleep 12
        curl -fsS ${routerUrl}/admin/pool | jq

        echo '→ Recover and start canary failback'
        curl -fsS -X POST http://app-${target}:8080/admin/inject-failure \
            -H 'content-type: application/json' \
            -d '{"mode":"none"}' | jq

        sleep 12
        curl -fsS -X POST ${routerUrl}/admin/canary/start \
            -H 'content-type: application/json' \
            -d '{"target":"${target}"}' | jq

        echo '→ Watch canary until terminal state'
        for i in \$(seq 1 60); do
            S=\$(curl -fsS ${routerUrl}/admin/canary/status)
            echo "\$S" | jq -c
            STATE=\$(echo "\$S" | jq -r .state)
            if [ "\$STATE" = "completed" ] || [ "\$STATE" = "rolled_back" ]; then
                if [ "\$STATE" = "rolled_back" ]; then
                    echo 'Canary rolled back during drill'; exit 1
                fi
                exit 0
            fi
            sleep 10
        done
        echo 'Canary did not terminate in time' >&2; exit 1
    """
}
