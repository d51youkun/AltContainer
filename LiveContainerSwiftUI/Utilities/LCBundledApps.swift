import Foundation

/// No Apple ID credentials are stored here. Each slot signs in inside AltStore.
enum LCBundledApps {
    static var usesAltStore: Bool {
        Bundle.main.object(forInfoDictionaryKey: "LCBuiltInStore") as? String == "AltStore"
    }

    static var stikIPA: URL? {
        let url = Bundle.main.bundleURL.appendingPathComponent("BundledApps/StikDebug.ipa")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    static var accountSlot: Int {
        get { min(3, max(1, UserDefaults.standard.integer(forKey: "LCAltStoreAccountSlot"))) }
        set { UserDefaults.standard.set(min(3, max(1, newValue)), forKey: "LCAltStoreAccountSlot") }
    }

    static var accountHome: URL {
        LCPath.docPath.appendingPathComponent("AltStore/Account\(accountSlot)")
    }

    static var keychainAccessGroup: String {
        "\(LCSharedUtils.teamIdentifier()!).com.kdt.livecontainer.shared.\(124 + accountSlot)"
    }

    static func prepareAccount() throws {
        let home = accountHome
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        let config: [String: Any] = [
            "appIdentifier": "com.rileytestut.AltStore",
            "keychainGroupId": 124 + accountSlot,
            "isolateAppGroup": true
        ]
        let data = try PropertyListSerialization.data(fromPropertyList: config, format: .binary, options: 0)
        try data.write(to: home.appendingPathComponent("LCContainerInfo.plist"), options: .atomic)
    }
}
