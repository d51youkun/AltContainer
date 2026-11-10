//
//  XPCClient.m
//  AltStore
//
//  Created by s s on 2025/7/20.
//  Copyright © 2025 SideStore. All rights reserved.
//
#include "XPCServer.h"
#include "../LiveContainer/utils.h"
#include "../LiveContainer/LCSharedUtils.h"
@import UIKit;

@interface SideStoreClient(Swift)
- (void)performRefreshForRealWithIdentifier:(NSString*)identifier
                            mangledTypeName:(NSString*)mangledTypeName
                                     server:(id <RefreshServer> _Nonnull)server;

@end

static LiveProcessSideStoreHandler* handler = nil;
void installSideStoreHooks(void);

@implementation SideStoreClient

+ (SideStoreClient*)shared {
    static SideStoreClient* sharedClient = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sharedClient = [SideStoreClient new];
    });

    return sharedClient;
}

+ (void)load {
    if(!NSUserDefaults.isSideStore) return;
    // AltStore is loaded through the same bootstrap path, but must never receive
    // SideStore-only runtime hooks (several selectors do not exist in AltStore).
    if ([NSUserDefaults.lcMainBundle.infoDictionary[@"LCBuiltInStore"] isEqualToString:@"AltStore"]) return;
    
    installSideStoreHooks();
    
    if(!NSUserDefaults.isLiveProcess) return;
    
    handler = [PrivClass(LiveProcessSideStoreHandler) shared];
    installSideStoreNotificationHooks();
    handler.connection.exportedInterface = [NSXPCInterface interfaceWithProtocol:@protocol(RefreshClient)];
    handler.connection.exportedObject = SideStoreClient.shared;

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(appDidFinishLaunching:)
                                                 name:UIApplicationDidFinishLaunchingNotification
                                               object:nil];
}

// Implement the callback method
+ (void)appDidFinishLaunching:(NSNotification *)notification {
    NSDictionary *launchOptions = notification.userInfo;
    [handler.server finishedLaunching];
}

- (void) relaunchLC {
    [LCSharedUtils launchToGuestAppWithClassicMode:0];
}

- (void)refreshAllAppsWithIdentifier:(NSString*)identifier mangledTypeName:(NSString *)mangledTypeName {
    if(!handler) {
        return;
    }
    [self performRefreshForRealWithIdentifier:identifier mangledTypeName:mangledTypeName server:handler.server];
}

@end
