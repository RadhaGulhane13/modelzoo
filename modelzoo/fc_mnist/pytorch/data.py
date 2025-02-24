# Copyright 2022 Cerebras Systems.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch
from torchvision import datasets, transforms

from modelzoo.common.pytorch import cb_model as cm
from modelzoo.common.pytorch.input_utils import get_streaming_batch_size
from modelzoo.common.pytorch.utils import SampleGenerator, get_input_dtype


def get_train_dataloader(params):
    """
    :param <dict> params: dict containing input parameters for creating dataset.
    Expects the following fields:

    - "data_dir" (string): path to the data files to use.
    - "batch_size" (int): batch size
    - "to_float16" (bool): whether to convert to float16 or not
    - "drop_last_batch" (bool): whether to drop the last batch or not
    """
    input_params = params["train_input"]
    use_cs = cm.use_cs() or cm.is_appliance()

    batch_size = get_streaming_batch_size(input_params.get("batch_size"))
    to_float16 = input_params.get("to_float16", True)
    dtype = get_input_dtype(to_float16)
    shuffle = input_params["shuffle"]

    if input_params.get("use_fake_data", False):
        num_streamers = cm.num_streamers() if cm.is_streamer() else 1
        train_loader = SampleGenerator(
            data=(
                torch.zeros(batch_size, 1, 28, 28, dtype=dtype),
                torch.zeros(
                    batch_size, dtype=torch.int32 if use_cs else torch.int64
                ),
            ),
            sample_count=60000 // batch_size // num_streamers,
        )
    else:
        train_dataset = datasets.MNIST(
            input_params["data_dir"],
            train=True,
            download=cm.is_master_ordinal(),
            transform=transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize((0.1307,), (0.3081,)),
                    transforms.Lambda(
                        lambda x: torch.as_tensor(x, dtype=dtype)
                    ),
                ]
            ),
            target_transform=transforms.Lambda(
                lambda x: torch.as_tensor(x, dtype=torch.int32)
            )
            if use_cs
            else None,
        )

        train_sampler = None
        if use_cs and cm.num_streamers() > 1 and cm.is_streamer():
            train_sampler = torch.utils.data.distributed.DistributedSampler(
                train_dataset,
                num_replicas=cm.num_streamers(),
                rank=cm.get_streaming_rank(),
                shuffle=shuffle,
            )
        else:
            train_sampler = None
        train_loader = torch.utils.data.DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=train_sampler,
            drop_last=input_params["drop_last_batch"],
            shuffle=False if train_sampler else shuffle,
            num_workers=input_params.get("num_workers", 0),
        )
    return train_loader


def get_eval_dataloader(params):
    input_params = params["eval_input"]
    use_cs = cm.use_cs() or cm.is_appliance()

    batch_size = get_streaming_batch_size(input_params.get("batch_size"))
    to_float16 = input_params.get("to_float16", True)
    dtype = get_input_dtype(to_float16)

    if input_params.get("use_fake_data", False):
        num_streamers = cm.num_streamers() if cm.is_streamer() else 1
        eval_loader = SampleGenerator(
            data=(
                torch.zeros(batch_size, 1, 28, 28, dtype=dtype),
                torch.zeros(
                    batch_size, dtype=torch.int32 if use_cs else torch.int64
                ),
            ),
            sample_count=10000 // batch_size // num_streamers,
        )
    else:
        eval_dataset = datasets.MNIST(
            input_params["data_dir"],
            train=False,
            download=cm.is_master_ordinal(),
            transform=transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize((0.1307,), (0.3081,)),
                    transforms.Lambda(
                        lambda x: torch.as_tensor(x, dtype=dtype)
                    ),
                ]
            ),
            target_transform=transforms.Lambda(
                lambda x: torch.as_tensor(x, dtype=torch.int32)
            )
            if use_cs
            else None,
        )

        eval_loader = torch.utils.data.DataLoader(
            eval_dataset,
            batch_size=batch_size,
            drop_last=input_params["drop_last_batch"],
            shuffle=False,
            num_workers=input_params.get("num_workers", 0),
        )
    return eval_loader
