# Stop + arrows: step Live's blue hand through the selected track's devices.
#
# Pure functions over Live objects, with no imports, so the self-test can load
# this file by path without a fake _Framework. MVave_SMC_STEPSEQ carries its
# own copy of the same walk (_device_list), because the two packages are
# installed separately and neither may depend on the other being present.


def device_list(track):
    """The track's devices in order, with the devices of each Drum Rack's
    selected pad right after the rack, as Live draws them."""
    found = []

    def walk(devices):
        for device in devices:
            found.append(device)
            if getattr(device, 'can_have_drum_pads', False):
                pad = device.view.selected_drum_pad
                for chain in (pad.chains if pad is not None else ()):
                    walk(chain.devices)

    walk(track.devices)
    return found


def step(items, current, delta):
    """The item delta places from current, stopping at both ends.

    An unknown current (a device nested deeper than the walk goes, say) lands
    on the first item rather than doing nothing, so the button always answers.
    Returns None for an empty list.
    """
    if not items:
        return None
    for index, item in enumerate(items):
        if item == current:
            return items[max(0, min(len(items) - 1, index + delta))]
    return items[0]


def track_list(song):
    """What the arrows step through: the same set MixerComponent's select
    buttons walk -- visible tracks, then returns, then the master."""
    return list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
