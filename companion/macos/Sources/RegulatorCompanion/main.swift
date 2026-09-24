import AppKit
import Foundation
import Security

private let keychainService = "io.github.misyukdima.openai-work-codex-regulator.companion"
private let installationKey = "installation_id"
private let deviceTokenKey = "device_token"

final class KeychainStore {
    func save(_ value: String, key: String) -> Bool {
        let data = Data(value.utf8)
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(base as CFDictionary)
        var add = base
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(add as CFDictionary, nil) == errSecSuccess
    }

    func load(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }
        return value
    }
}

struct PairingSession {
    let pairingID: String
    let verifier: String
    let installationID: String
    let deviceToken: String
    let connectURL: URL
}

final class RelayClient {
    private let baseURL: URL
    private let session: URLSession

    init?(baseURLString: String) {
        guard let url = URL(string: baseURLString),
              url.scheme?.lowercased() == "https" else {
            return nil
        }
        self.baseURL = url
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 12
        config.timeoutIntervalForResource = 20
        self.session = URLSession(configuration: config)
    }

    private func endpoint(_ path: String) -> URL {
        baseURL.appendingPathComponent(path)
    }

    func startPairing(completion: @escaping (Result<PairingSession, Error>) -> Void) {
        var request = URLRequest(url: endpoint("v1/pairings"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = Data("{}".utf8)

        session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode),
                  let data = data,
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let pairingID = object["pairing_id"] as? String,
                  let verifier = object["pairing_verifier"] as? String,
                  let installationID = object["installation_id"] as? String,
                  let deviceToken = object["device_token"] as? String,
                  let connectURLString = object["connect_url"] as? String,
                  let connectURL = URL(string: connectURLString),
                  connectURL.scheme?.lowercased() == "https" else {
                completion(.failure(NSError(domain: "RegulatorCompanion", code: 10, userInfo: [NSLocalizedDescriptionKey: "Relay вернул некорректный pairing response."])))
                return
            }
            completion(.success(PairingSession(
                pairingID: pairingID,
                verifier: verifier,
                installationID: installationID,
                deviceToken: deviceToken,
                connectURL: connectURL
            )))
        }.resume()
    }

    func pairingStatus(_ pairing: PairingSession, completion: @escaping (Result<String, Error>) -> Void) {
        var request = URLRequest(url: endpoint("v1/pairings/\(pairing.pairingID)"))
        request.httpMethod = "GET"
        request.setValue("Pairing \(pairing.verifier)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode),
                  let data = data,
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let status = object["status"] as? String else {
                completion(.failure(NSError(domain: "RegulatorCompanion", code: 11, userInfo: [NSLocalizedDescriptionKey: "Не удалось проверить pairing."])))
                return
            }
            completion(.success(status))
        }.resume()
    }

    func pushSnapshot(installationID: String, deviceToken: String, envelope: [String: Any], completion: @escaping (Result<Void, Error>) -> Void) {
        guard JSONSerialization.isValidJSONObject(envelope),
              let body = try? JSONSerialization.data(withJSONObject: envelope) else {
            completion(.failure(NSError(domain: "RegulatorCompanion", code: 12, userInfo: [NSLocalizedDescriptionKey: "Некорректный quota snapshot."])))
            return
        }
        var request = URLRequest(url: endpoint("v1/installations/\(installationID)/snapshot"))
        request.httpMethod = "PUT"
        request.setValue("Bearer \(deviceToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = body
        session.dataTask(with: request) { _, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode) else {
                completion(.failure(NSError(domain: "RegulatorCompanion", code: 13, userInfo: [NSLocalizedDescriptionKey: "Relay отклонил quota snapshot."])))
                return
            }
            completion(.success(()))
        }.resume()
    }
}

final class CodexBarSensor {
    private let fiveHourMinutes = 300
    private let weeklyMinutes = 10_080

    func helperURL() -> URL? {
        if let bundled = Bundle.main.url(forAuxiliaryExecutable: "CodexBarCLI") {
            return bundled
        }
        let candidates = [
            "/Applications/CodexBar.app/Contents/Helpers/CodexBarCLI",
            "/usr/local/bin/codexbar",
            "/opt/homebrew/bin/codexbar",
        ]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        return nil
    }

    func collect(completion: @escaping (Result<[String: Any], Error>) -> Void) {
        guard let helper = helperURL() else {
            completion(.failure(NSError(domain: "RegulatorCompanion", code: 20, userInfo: [NSLocalizedDescriptionKey: "Quota sensor не найден в сборке."])))
            return
        }

        DispatchQueue.global(qos: .utility).async {
            let process = Process()
            let stdout = Pipe()
            let stderr = Pipe()
            process.executableURL = helper
            process.arguments = [
                "usage", "--provider", "codex", "--source", "oauth",
                "--format", "json", "--json-only", "--no-color"
            ]
            process.standardOutput = stdout
            process.standardError = stderr
            var env = ProcessInfo.processInfo.environment
            env["NO_COLOR"] = "1"
            env.removeValue(forKey: "OPENAI_API_KEY")
            env.removeValue(forKey: "ANTHROPIC_API_KEY")
            process.environment = env

            do {
                try process.run()
            } catch {
                completion(.failure(error))
                return
            }
            process.waitUntilExit()
            guard process.terminationStatus == 0 else {
                completion(.failure(NSError(domain: "RegulatorCompanion", code: 21, userInfo: [NSLocalizedDescriptionKey: "Не удалось прочитать текущую квоту."])))
                return
            }
            let data = stdout.fileHandleForReading.readDataToEndOfFile()
            do {
                let raw = try JSONSerialization.jsonObject(with: data)
                let snapshot = try self.normalize(raw)
                completion(.success(snapshot))
            } catch {
                completion(.failure(error))
            }
        }
    }

    private func selectCodexResult(_ raw: Any) throws -> [String: Any] {
        if let object = raw as? [String: Any] {
            return object
        }
        if let array = raw as? [[String: Any]] {
            let matches = array.filter { (($0["provider"] as? String) ?? "").lowercased() == "codex" }
            if matches.count == 1 { return matches[0] }
            if matches.isEmpty, array.count == 1 { return array[0] }
        }
        throw NSError(domain: "RegulatorCompanion", code: 22, userInfo: [NSLocalizedDescriptionKey: "Неоднозначный Codex quota payload."])
    }

    private func minutes(_ window: [String: Any]) -> Int? {
        if let value = window["windowMinutes"] as? NSNumber { return value.intValue }
        if let value = window["window_minutes"] as? NSNumber { return value.intValue }
        if let value = window["limit_window_seconds"] as? NSNumber { return Int(round(value.doubleValue / 60.0)) }
        if let value = window["windowSeconds"] as? NSNumber { return Int(round(value.doubleValue / 60.0)) }
        return nil
    }

    private func usedPercent(_ window: [String: Any]) -> Double? {
        let raw = window["usedPercent"] ?? window["used_percent"]
        guard let value = raw as? NSNumber else { return nil }
        let number = value.doubleValue
        return (0...100).contains(number) ? number : nil
    }

    private func resetValue(_ window: [String: Any]) -> Any {
        window["resetsAt"] ?? window["reset_at"] ?? window["resetAt"] ?? NSNull()
    }

    private func normalize(_ raw: Any) throws -> [String: Any] {
        let result = try selectCodexResult(raw)
        let usage = (result["usage"] as? [String: Any]) ?? result
        var windows: [[String: Any]] = []
        for key in ["primary", "secondary", "primaryWindow", "secondaryWindow"] {
            if let value = usage[key] as? [String: Any] { windows.append(value) }
        }
        let rateLimit = (usage["rate_limit"] as? [String: Any]) ?? (result["rate_limit"] as? [String: Any])
        if let rateLimit = rateLimit {
            for key in ["primary_window", "secondary_window"] {
                if let value = rateLimit[key] as? [String: Any] { windows.append(value) }
            }
        }
        guard !windows.isEmpty else {
            throw NSError(domain: "RegulatorCompanion", code: 23, userInfo: [NSLocalizedDescriptionKey: "Quota windows отсутствуют."])
        }

        var weeklyUsed: Double?
        var weeklyReset: Any = NSNull()
        var fiveUsed: Double?
        var fiveReset: Any = NSNull()
        var other: [[String: Any]] = []

        for window in windows {
            guard let duration = minutes(window), let used = usedPercent(window) else { continue }
            if duration == weeklyMinutes {
                if weeklyUsed != nil { throw NSError(domain: "RegulatorCompanion", code: 24, userInfo: [NSLocalizedDescriptionKey: "Несколько weekly windows."]) }
                weeklyUsed = used
                weeklyReset = resetValue(window)
            } else if duration == fiveHourMinutes {
                if fiveUsed != nil { throw NSError(domain: "RegulatorCompanion", code: 25, userInfo: [NSLocalizedDescriptionKey: "Несколько 5-hour windows."]) }
                fiveUsed = used
                fiveReset = resetValue(window)
            } else {
                other.append([
                    "kind": "OTHER_WINDOW",
                    "used_percent": used,
                    "window_minutes": duration,
                    "reset_at": resetValue(window),
                ])
            }
        }

        let source = ((result["source"] as? String) ?? "unknown").uppercased()
        let updatedAt = (usage["updatedAt"] as? String)
            ?? (usage["updated_at"] as? String)
            ?? (result["updatedAt"] as? String)
            ?? (result["updated_at"] as? String)

        let snapshot: [String: Any] = [
            "schema_version": 1,
            "allowance_domain": "WORK_CODEX",
            "source": "CODEXBAR_\(source)",
            "sensor": "CODEXBAR",
            "snapshot_at": updatedAt ?? NSNull(),
            "freshness": updatedAt == nil ? "UNKNOWN" : "FRESH",
            "age_seconds": NSNull(),
            "weekly_meter_semantics": "USED",
            "weekly_used": weeklyUsed ?? NSNull(),
            "weekly_reset": weeklyReset,
            "five_hour_used": fiveUsed ?? NSNull(),
            "five_hour_reset": fiveReset,
            "other_windows": other,
        ]
        return ["schema_version": 1, "snapshot": snapshot]
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let keychain = KeychainStore()
    private let sensor = CodexBarSensor()
    private var relay: RelayClient?
    private var pairing: PairingSession?
    private var pollAttempts = 0
    private var refreshTimer: Timer?

    private let window = NSWindow(
        contentRect: NSRect(x: 0, y: 0, width: 470, height: 310),
        styleMask: [.titled, .closable, .miniaturizable],
        backing: .buffered,
        defer: false
    )
    private let titleLabel = NSTextField(labelWithString: "OpenAI Work + Codex Regulator")
    private let chatLabel = NSTextField(labelWithString: "ChatGPT: проверка...")
    private let sensorLabel = NSTextField(labelWithString: "Quota telemetry: проверка...")
    private let updateLabel = NSTextField(labelWithString: "Последнее обновление: —")
    private let messageLabel = NSTextField(wrappingLabelWithString: "")
    private let connectButton = NSButton(title: "Подключить ChatGPT", target: nil, action: nil)
    private let refreshButton = NSButton(title: "Проверить сейчас", target: nil, action: nil)

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        configureWindow()
        configureRelay()
        refreshStatus()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        refreshTimer?.invalidate()
    }

    private func configureWindow() {
        window.title = "Regulator Companion"
        window.isReleasedWhenClosed = false

        titleLabel.font = NSFont.systemFont(ofSize: 20, weight: .semibold)
        messageLabel.textColor = .secondaryLabelColor
        messageLabel.maximumNumberOfLines = 3

        connectButton.target = self
        connectButton.action = #selector(connectPressed)
        connectButton.bezelStyle = .rounded
        refreshButton.target = self
        refreshButton.action = #selector(refreshPressed)
        refreshButton.bezelStyle = .rounded

        let buttons = NSStackView(views: [connectButton, refreshButton])
        buttons.orientation = .horizontal
        buttons.spacing = 10

        let stack = NSStackView(views: [titleLabel, chatLabel, sensorLabel, updateLabel, messageLabel, buttons])
        stack.orientation = .vertical
        stack.spacing = 14
        stack.alignment = .leading
        stack.translatesAutoresizingMaskIntoConstraints = false

        let container = NSView()
        container.addSubview(stack)
        window.contentView = container
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 28),
            stack.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -28),
            stack.topAnchor.constraint(equalTo: container.topAnchor, constant: 28),
        ])
    }

    private func configureRelay() {
        guard let relayURL = Bundle.main.object(forInfoDictionaryKey: "RegulatorRelayBaseURL") as? String,
              !relayURL.isEmpty,
              let client = RelayClient(baseURLString: relayURL) else {
            relay = nil
            messageLabel.stringValue = "Development build: production relay ещё не настроен."
            connectButton.isEnabled = false
            return
        }
        relay = client
        connectButton.isEnabled = true
    }

    private func refreshStatus() {
        sensorLabel.stringValue = sensor.helperURL() == nil
            ? "Quota telemetry: sensor не найден"
            : "Quota telemetry: готова"

        if keychain.load(installationKey) != nil, keychain.load(deviceTokenKey) != nil {
            chatLabel.stringValue = "ChatGPT: подключён"
            connectButton.title = "Переподключить"
            scheduleBackgroundRefresh()
            refreshAndPush()
        } else {
            chatLabel.stringValue = "ChatGPT: не подключён"
            connectButton.title = "Подключить ChatGPT"
        }
    }

    private func scheduleBackgroundRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            self?.refreshAndPush()
        }
    }

    @objc private func connectPressed() {
        guard let relay = relay else { return }
        connectButton.isEnabled = false
        messageLabel.stringValue = "Создаю безопасное подключение..."
        relay.startPairing { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .failure:
                    self.messageLabel.stringValue = "Не удалось начать подключение. Повторите позже."
                    self.connectButton.isEnabled = true
                case .success(let pairing):
                    self.pairing = pairing
                    self.pollAttempts = 0
                    self.messageLabel.stringValue = "Подтвердите подключение в открывшемся окне браузера."
                    NSWorkspace.shared.open(pairing.connectURL)
                    self.pollPairing()
                }
            }
        }
    }

    private func pollPairing() {
        guard let relay = relay, let pairing = pairing else { return }
        pollAttempts += 1
        if pollAttempts > 150 {
            messageLabel.stringValue = "Время подключения истекло. Нажмите «Подключить ChatGPT» ещё раз."
            connectButton.isEnabled = true
            self.pairing = nil
            return
        }

        relay.pairingStatus(pairing) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .failure:
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { self.pollPairing() }
                case .success(let status):
                    if status == "CLAIMED" {
                        guard self.keychain.save(pairing.installationID, key: installationKey),
                              self.keychain.save(pairing.deviceToken, key: deviceTokenKey) else {
                            self.messageLabel.stringValue = "Не удалось сохранить подключение в Keychain."
                            self.connectButton.isEnabled = true
                            return
                        }
                        self.chatLabel.stringValue = "ChatGPT: подключён"
                        self.messageLabel.stringValue = "Готово. Квота будет обновляться автоматически."
                        self.connectButton.title = "Переподключить"
                        self.connectButton.isEnabled = true
                        self.pairing = nil
                        self.scheduleBackgroundRefresh()
                        self.refreshAndPush()
                    } else {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { self.pollPairing() }
                    }
                }
            }
        }
    }

    @objc private func refreshPressed() {
        refreshAndPush()
    }

    private func refreshAndPush() {
        refreshButton.isEnabled = false
        sensor.collect { [weak self] result in
            guard let self = self else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async {
                    self.sensorLabel.stringValue = "Quota telemetry: ошибка чтения"
                    self.messageLabel.stringValue = "Не удалось получить текущую квоту."
                    self.refreshButton.isEnabled = true
                }
            case .success(let envelope):
                guard let relay = self.relay,
                      let installationID = self.keychain.load(installationKey),
                      let deviceToken = self.keychain.load(deviceTokenKey) else {
                    DispatchQueue.main.async {
                        self.sensorLabel.stringValue = "Quota telemetry: локально готова"
                        self.messageLabel.stringValue = "Подключите ChatGPT, чтобы передавать квоту автоматически."
                        self.refreshButton.isEnabled = true
                    }
                    return
                }
                relay.pushSnapshot(installationID: installationID, deviceToken: deviceToken, envelope: envelope) { pushResult in
                    DispatchQueue.main.async {
                        switch pushResult {
                        case .success:
                            self.sensorLabel.stringValue = "Quota telemetry: работает"
                            let formatter = DateFormatter()
                            formatter.dateStyle = .none
                            formatter.timeStyle = .medium
                            self.updateLabel.stringValue = "Последнее обновление: \(formatter.string(from: Date()))"
                            self.messageLabel.stringValue = "Квота синхронизирована с Regulator."
                        case .failure:
                            self.sensorLabel.stringValue = "Quota telemetry: relay недоступен"
                            self.messageLabel.stringValue = "Локальная квота получена, но не удалось синхронизировать её с ChatGPT."
                        }
                        self.refreshButton.isEnabled = true
                    }
                }
            }
        }
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.run()
