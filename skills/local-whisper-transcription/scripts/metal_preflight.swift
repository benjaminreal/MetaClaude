import Metal

guard let device = MTLCreateSystemDefaultDevice() else {
    FileHandle.standardError.write(Data("Metal device unavailable\n".utf8))
    exit(1)
}

print(device.name)
