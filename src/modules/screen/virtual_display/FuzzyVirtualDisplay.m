// Fuzzy Macro virtual display helper.
//
// Creates a virtual display for Roblox to run on and shows a live preview of
// it in a window, so the macro can drive Roblox without taking over the
// user's real screen. Based on DeskPad by Bastian Andelefski
// (https://github.com/Stengo/DeskPad, MIT License).
//
// Usage: FuzzyVirtualDisplay [--width 1920] [--height 1080] [--parent-pid PID]
//                            [--name NAME] [--no-preview]
//
// Prints "READY <displayID>" on stdout once the display exists. The display is
// removed when this process exits, which happens on SIGTERM/SIGINT or when the
// parent process goes away.
//
// Build: clang -fobjc-arc -framework Cocoa -framework CoreGraphics
//        -framework IOSurface FuzzyVirtualDisplay.m -o FuzzyVirtualDisplay

#import <Cocoa/Cocoa.h>
#import <CoreGraphics/CoreGraphics.h>
#import <IOSurface/IOSurface.h>
#import <objc/message.h>
#include <signal.h>
#include <unistd.h>

// CGVirtualDisplay is private CoreGraphics API. The interfaces below match
// DeskPad's CGVirtualDisplayPrivate.h. The classes are looked up at runtime so
// the helper still links on SDKs that do not export them.
@class CGVirtualDisplay;

@interface CGVirtualDisplayDescriptor : NSObject
@property(retain, nonatomic) NSString *name;
@property(nonatomic) unsigned int maxPixelsHigh;
@property(nonatomic) unsigned int maxPixelsWide;
@property(nonatomic) CGSize sizeInMillimeters;
@property(nonatomic) unsigned int serialNum;
@property(nonatomic) unsigned int productID;
@property(nonatomic) unsigned int vendorID;
@property(copy, nonatomic) void (^terminationHandler)(id, CGVirtualDisplay *);
- (void)setDispatchQueue:(dispatch_queue_t)queue;
@end

@interface CGVirtualDisplayMode : NSObject
- (instancetype)initWithWidth:(NSUInteger)width height:(NSUInteger)height refreshRate:(CGFloat)refreshRate;
@end

@interface CGVirtualDisplaySettings : NSObject
@property(retain, nonatomic) NSArray *modes;
@property(nonatomic) unsigned int hiDPI;
@end

@interface CGVirtualDisplay : NSObject
@property(readonly, nonatomic) CGDirectDisplayID displayID;
- (instancetype)initWithDescriptor:(CGVirtualDisplayDescriptor *)descriptor;
- (BOOL)applySettings:(CGVirtualDisplaySettings *)settings;
@end

// Stable IDs so macOS (and ColorSync) recognise the display between launches.
static const unsigned int kVendorID = 0x4655; // "FU"
static const unsigned int kProductID = 0x5A5A;
static const unsigned int kSerialNum = 0x0001;
static NSString *const kPreviewFrameKey = @"PreviewWindowFrame";

static void setPrimary(id descriptor, NSString *selectorName, CGPoint point) {
    // Newer macOS releases let the descriptor carry chromaticity primaries.
    // Use the sRGB primaries where supported; older releases ignore this.
    SEL selector = NSSelectorFromString(selectorName);
    if ([descriptor respondsToSelector:selector]) {
        ((void (*)(id, SEL, CGPoint))objc_msgSend)(descriptor, selector, point);
    }
}

@interface PreviewView : NSView
@property(nonatomic) CGDirectDisplayID displayID;
@property(nonatomic) CGSize resolution;
@end

@implementation PreviewView

- (instancetype)initWithFrame:(NSRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.wantsLayer = YES;
        self.layer.backgroundColor = NSColor.blackColor.CGColor;
        self.layer.contentsGravity = kCAGravityResizeAspect;
    }
    return self;
}

- (BOOL)acceptsFirstMouse:(NSEvent *)event {
    return YES;
}

- (void)mouseUp:(NSEvent *)event {
    // Like DeskPad: clicking the preview moves the cursor to the same point
    // on the virtual display.
    NSPoint clicked = [self convertPoint:event.locationInWindow fromView:nil];
    NSSize viewSize = self.bounds.size;
    if (viewSize.width <= 0 || viewSize.height <= 0) {
        return;
    }
    CGFloat scale = MIN(viewSize.width / self.resolution.width, viewSize.height / self.resolution.height);
    CGFloat drawnWidth = self.resolution.width * scale;
    CGFloat drawnHeight = self.resolution.height * scale;
    CGFloat x = (clicked.x - (viewSize.width - drawnWidth) / 2) / scale;
    CGFloat y = (viewSize.height - clicked.y - (viewSize.height - drawnHeight) / 2) / scale;
    if (x < 0 || y < 0 || x >= self.resolution.width || y >= self.resolution.height) {
        return;
    }
    CGDisplayMoveCursorToPoint(self.displayID, CGPointMake(x, y));
}

@end

@interface AppDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property(nonatomic) NSUInteger width;
@property(nonatomic) NSUInteger height;
@property(nonatomic) pid_t parentPID;
@property(nonatomic, copy) NSString *displayName;
@property(nonatomic) BOOL showPreview;
@property(nonatomic, strong) CGVirtualDisplay *display;
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic) CGDisplayStreamRef stream;
@property(nonatomic, strong) NSTimer *parentTimer;
@end

@implementation AppDelegate

- (BOOL)createDisplay {
    Class descriptorClass = NSClassFromString(@"CGVirtualDisplayDescriptor");
    Class displayClass = NSClassFromString(@"CGVirtualDisplay");
    Class settingsClass = NSClassFromString(@"CGVirtualDisplaySettings");
    Class modeClass = NSClassFromString(@"CGVirtualDisplayMode");
    if (!descriptorClass || !displayClass || !settingsClass || !modeClass) {
        fprintf(stderr, "Virtual displays are not supported on this version of macOS\n");
        return NO;
    }

    CGVirtualDisplayDescriptor *descriptor = [[descriptorClass alloc] init];
    [descriptor setDispatchQueue:dispatch_get_main_queue()];
    descriptor.name = self.displayName;
    descriptor.maxPixelsWide = (unsigned int)self.width;
    descriptor.maxPixelsHigh = (unsigned int)self.height;
    // Roughly a 24" panel (~92 PPI) so macOS treats it as a standard,
    // non-retina display at 100% scaling with default text size.
    descriptor.sizeInMillimeters = CGSizeMake(self.width * 0.2745, self.height * 0.2745);
    descriptor.vendorID = kVendorID;
    descriptor.productID = kProductID;
    descriptor.serialNum = kSerialNum;
    setPrimary(descriptor, @"setRedPrimary:", CGPointMake(0.64, 0.33));
    setPrimary(descriptor, @"setGreenPrimary:", CGPointMake(0.30, 0.60));
    setPrimary(descriptor, @"setBluePrimary:", CGPointMake(0.15, 0.06));
    setPrimary(descriptor, @"setWhitePoint:", CGPointMake(0.3127, 0.3290));
    descriptor.terminationHandler = ^(id _, CGVirtualDisplay *display) {
        fprintf(stderr, "Virtual display was terminated by the system\n");
        exit(1);
    };

    CGVirtualDisplay *display = [[displayClass alloc] initWithDescriptor:descriptor];
    if (!display || display.displayID == 0) {
        fprintf(stderr, "Failed to create the virtual display\n");
        return NO;
    }

    // A single non-HiDPI mode: 1 point == 1 pixel (100% scaling), and no
    // scaled "larger text"/"more space" variants for macOS to pick.
    CGVirtualDisplaySettings *settings = [[settingsClass alloc] init];
    settings.hiDPI = 0;
    settings.modes = @[[[modeClass alloc] initWithWidth:self.width height:self.height refreshRate:60]];
    if (![display applySettings:settings]) {
        fprintf(stderr, "Failed to apply the virtual display settings\n");
        return NO;
    }
    self.display = display;
    return YES;
}

- (void)createPreviewWindow {
    NSRect mainFrame = NSScreen.mainScreen.visibleFrame;
    CGFloat previewWidth = MIN(self.width / 2.0, mainFrame.size.width * 0.5);
    CGFloat previewHeight = previewWidth * self.height / self.width;
    NSRect frame = NSMakeRect(0, 0, previewWidth, previewHeight);

    NSWindowStyleMask style = NSWindowStyleMaskTitled | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable;
    NSWindow *window = [[NSWindow alloc] initWithContentRect:frame styleMask:style backing:NSBackingStoreBuffered defer:NO];
    window.title = self.displayName;
    window.releasedWhenClosed = NO;
    window.contentAspectRatio = NSMakeSize(self.width, self.height);
    window.contentMinSize = NSMakeSize(320, 320.0 * self.height / self.width);
    window.collectionBehavior |= NSWindowCollectionBehaviorFullScreenNone;

    PreviewView *view = [[PreviewView alloc] initWithFrame:frame];
    view.displayID = self.display.displayID;
    view.resolution = CGSizeMake(self.width, self.height);
    window.contentView = view;

    // Restore the last position the user gave the preview, else center it.
    NSString *savedFrame = [NSUserDefaults.standardUserDefaults stringForKey:kPreviewFrameKey];
    if (savedFrame) {
        [window setFrameFromString:savedFrame];
    } else {
        NSRect windowFrame = [window frameRectForContentRect:frame];
        windowFrame.origin.x = NSMidX(mainFrame) - windowFrame.size.width / 2;
        windowFrame.origin.y = NSMidY(mainFrame) - windowFrame.size.height / 2;
        [window setFrame:windowFrame display:NO];
    }
    window.delegate = self;
    // Show the preview without stealing focus from Roblox.
    [window orderFrontRegardless];
    self.window = window;

    NSDictionary *properties = @{(__bridge NSString *)kCGDisplayStreamShowCursor: @YES};
    __weak PreviewView *weakView = view;
    CGDisplayStreamRef stream = CGDisplayStreamCreateWithDispatchQueue(
        self.display.displayID, self.width, self.height, 'BGRA',
        (__bridge CFDictionaryRef)properties, dispatch_get_main_queue(),
        ^(CGDisplayStreamFrameStatus status, uint64_t time, IOSurfaceRef surface, CGDisplayStreamUpdateRef update) {
            if (status == kCGDisplayStreamFrameStatusFrameComplete && surface) {
                weakView.layer.contents = (__bridge id)surface;
            }
        });
    if (!stream) {
        fprintf(stderr, "Failed to start the preview (is Screen Recording allowed?)\n");
        return;
    }
    self.stream = stream;
    CGDisplayStreamStart(stream);
}

- (void)savePreviewFrame {
    // Only remember positions on a real screen. If the preview ends up on the
    // virtual display (e.g. moved there by a script) the user couldn't see it.
    NSNumber *screenID = self.window.screen.deviceDescription[@"NSScreenNumber"];
    if (!screenID || screenID.unsignedIntValue == self.display.displayID) {
        return;
    }
    [NSUserDefaults.standardUserDefaults setObject:[self.window stringWithSavedFrame] forKey:kPreviewFrameKey];
}

- (void)windowDidMove:(NSNotification *)notification {
    [self savePreviewFrame];
}

- (void)windowDidEndLiveResize:(NSNotification *)notification {
    [self savePreviewFrame];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    if (![self createDisplay]) {
        exit(2);
    }
    if (self.showPreview) {
        [self createPreviewWindow];
    }

    printf("READY %u\n", self.display.displayID);
    fflush(stdout);

    if (self.parentPID > 0) {
        self.parentTimer = [NSTimer scheduledTimerWithTimeInterval:1.0 repeats:YES block:^(NSTimer *timer) {
            if (getppid() != self.parentPID || kill(self.parentPID, 0) != 0) {
                [NSApp terminate:nil];
            }
        }];
    }
}

- (void)applicationWillTerminate:(NSNotification *)notification {
    if (self.stream) {
        CGDisplayStreamStop(self.stream);
        CFRelease(self.stream);
        self.stream = NULL;
    }
    self.display = nil;
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return NO;
}

@end

static dispatch_source_t installSignalHandler(int sig) {
    signal(sig, SIG_IGN);
    dispatch_source_t source = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, sig, 0, dispatch_get_main_queue());
    dispatch_source_set_event_handler(source, ^{
        [NSApp terminate:nil];
    });
    dispatch_resume(source);
    return source;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        AppDelegate *delegate = [[AppDelegate alloc] init];
        delegate.width = 1920;
        delegate.height = 1080;
        delegate.displayName = @"Fuzzy Macro Display";
        delegate.showPreview = YES;

        for (int i = 1; i < argc; i++) {
            NSString *arg = [NSString stringWithUTF8String:argv[i]];
            NSString *value = i + 1 < argc ? [NSString stringWithUTF8String:argv[i + 1]] : nil;
            if ([arg isEqualToString:@"--width"] && value) {
                delegate.width = (NSUInteger)MAX(640, value.integerValue);
                i++;
            } else if ([arg isEqualToString:@"--height"] && value) {
                delegate.height = (NSUInteger)MAX(480, value.integerValue);
                i++;
            } else if ([arg isEqualToString:@"--parent-pid"] && value) {
                delegate.parentPID = (pid_t)value.intValue;
                i++;
            } else if ([arg isEqualToString:@"--name"] && value) {
                delegate.displayName = value;
                i++;
            } else if ([arg isEqualToString:@"--no-preview"]) {
                delegate.showPreview = NO;
            }
        }

        dispatch_source_t termSource = installSignalHandler(SIGTERM);
        dispatch_source_t intSource = installSignalHandler(SIGINT);

        NSApplication *app = NSApplication.sharedApplication;
        // No Dock icon or menu bar takeover; the preview window is enough.
        app.activationPolicy = NSApplicationActivationPolicyAccessory;
        app.delegate = delegate;
        [app run];
        (void)termSource;
        (void)intSource;
    }
    return 0;
}
